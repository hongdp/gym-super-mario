from numpy import random
import operator
from util import *


class QLearningAlgorithm():
    def __init__(self, options, actions, discount, featureExtractor):
        self.actions = actions
        self.discount = discount
        self.featureExtractor = featureExtractor
        self.updateInterval = 10  # number of frames to retrain the model
        self.updateTargetInterval = 50 # number of updates to update the target network
        self.updateCounter = 0
        self.updateTargetCounter = 0
        self.batchSize = 20
        self.batchPerFeedback = 5
        self.statecache = [[]]  # list of states for each game. A state is a window of frames
        self.actioncache = [[]]  # list of actions for each game
        self.actioncacheSize = [0]  # list of actions for each game
        self.options = options
        self.model = None
        self.explorationProb = 0.05
        self.softmaxExplore = options.softmaxExploration

    def set_model(self, model):
        self.model = model

    # Return the Q function associated with the weights and features
    def getQ(self, vs, state):
        if self.model.conv:
            tile, info = self.featureExtractor(state)
            scores = self.model.inference_Q(vs, [info], tile=[tile])[0]
        else:
            info = self.featureExtractor(state)
            if info is None:
                return [0]
            scores = self.model.inference_Q(vs, [info])[0]
        return scores

    def getProb(self, state):
        if self.model.conv:
            tile, info = self.featureExtractor(state)
            scores = self.model.inference_Prob([info], tile=[tile])[0]
        else:
            info = self.featureExtractor(state)
            if info is None:
                return [1.0 / len(self.actions)] * len(self.actions)
            scores = self.model.inference_Prob([info])[0]
        return scores

    # This algorithm will produce an action given a state.
    # Here we use the epsilon-greedy algorithm: with probability
    # |explorationProb|, take a random action.
    def getAction(self, state):
        actionIdx = 0
        if self.options.isTrain:
            rand = random.random()
            if rand < self.explorationProb:
                actionIdx = random.choice(range(len(self.actions)))
                print "randomly select action: {}".format(self.actions[actionIdx])
            else:
                if self.softmaxExplore:
                    prob = self.getProb(state)
                    actionIdx = random.choice(range(len(self.actions)), p=prob)
                    print "Prob: {} selected action: {}".format(prob, self.actions[actionIdx])
                else:
                    q = self.getQ(self.model.prediction_vs, state)
                    actionIdx, _ = max(enumerate(q), key=operator.itemgetter(1))
                    print "Q: {} best action: {}".format(q, self.actions[actionIdx])
        # probs = self.getProb(state)  # soft max prob
        #    actionIdx = random.choice(range(len(self.actions)),
        #                              p=probs)
        #    print "randomly select action id: {}".format(actionIdx)
        #    print "Probs: {}".format(probs)
        else:
            actionIdx, q = max(enumerate(self.getQ(self.model.prediction_vs, state)), key=operator.itemgetter(1))
            print "Q: {} best action: {}".format(q, self.actions[actionIdx])
        return Action.act(self.actions[actionIdx]), actionIdx

    # Call this function to get the step size to update the weights.

    def sample(self, sampleSize):
        # randomly choose a game and get its states
        samples = []
        gameLenSum = float(sum(self.actioncacheSize))
        gameProb = [length / gameLenSum for length in self.actioncacheSize]
        for i in range(sampleSize):
            gameIdx = random.choice(range(0, len(self.statecache)), p=gameProb)
            # Should have cache of s0, a0, ....., sn, an, sn+1, where reward of an is stored in sn+1
            gameStates = self.statecache[gameIdx]
            gameActions = self.actioncache[gameIdx]

            if len(gameActions) == 0:
                return self.sample()  # resample a different game

            # randomly choose a state except last one in the game
            stateIdx = random.randint(0, len(gameActions)) if len(gameActions) > 1 else 0

            state_n = gameStates[stateIdx]
            if self.model.conv:
                tile, info = self.featureExtractor(state_n)
            else:
                tile = None
                info = self.featureExtractor(state_n)
            action = gameActions[stateIdx]

            state_np1 = gameStates[stateIdx + 1]
            reward = state_np1.get_last_frame().get_reward()
            Vopt = max(self.getQ(self.model.target_vs, state_np1))
            gamma = self.discount
            target = (reward + gamma * Vopt)
            if state_np1.get_last_frame().get_info()['life'] == 0:
                target = reward

            samples.append((tile, info, action, target))

        return samples

    # once a while train the model
    def incorporateFeedback(self):
        if not self.options.isTrain: return

        self.updateCounter += 1
        if self.updateCounter < self.updateInterval:
            return
        self.updateCounter = 0

        print('incorporateFeedback ...')
        for i in range(self.batchPerFeedback):
            tiles = []  # a list of None if self.mode.conv is False
            infos = []
            actions = []
            target_Qs = []
            samples = self.sample(self.batchSize)
            for tile, info, action, target in samples:
                tiles.append(tile)
                infos.append(info)
                actions.append(action)
                target_Qs.append(target)

            self.model.update_weights(tiles=tiles, infos=infos, actions=actions, target_Qs=target_Qs)

        self.updateTargetCounter += 1
        if self.updateTargetCounter < self.updateTargetInterval:
            return
        self.updateTargetCounter = 0
        print('Updating Target Network ...')
        self.model.update_target_network()
