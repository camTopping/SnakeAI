import torch
import random
import numpy as np
from collections import deque
from snake_ai import SnakeGameAI, Direction, Point
from model import Linear_QNet, QTrainer
from helper import plot

BLOCK_SIZE = 20
MAX_MEMORY = 100_000
BATCH_SIZE = 1000
LR = 0.001  # Learning Rate
HIDDEN_LAYER = 256  # TODO: Experiment


class Agent:
    def __init__(self):
        self.n_games = 0
        self.epsilon = 0  # randomness
        self.gamma = 0.9  # discount rate [0,1)
        self.memory = deque(maxlen=MAX_MEMORY)  # automatically calls popleft()
        self.model = Linear_QNet(11, HIDDEN_LAYER, 3)  # 11 inputs, 3 outputs
        self.trainer = QTrainer(self.model, lr=LR, gamma=self.gamma)

    def get_state(self, game):
        # 11 Values:
        # Danger Straight, Right and Left
        # Direction Left, Right, Up and Down
        # Food Left, Right Up and Down
        head = game.snake[0]

        # Set up points around the snake to check for dangers
        point_l = Point(head.x - BLOCK_SIZE, head.y)
        point_r = Point(head.x + BLOCK_SIZE, head.y)
        point_u = Point(head.x, head.y - BLOCK_SIZE)
        point_d = Point(head.x, head.y + BLOCK_SIZE)

        dir_l = game.direction == Direction.LEFT
        dir_r = game.direction == Direction.RIGHT
        dir_u = game.direction == Direction.UP
        dir_d = game.direction == Direction.DOWN

        state = [
            # Danger straight
            (dir_r and game.is_collision(point_r)) or
            (dir_l and game.is_collision(point_l)) or
            (dir_u and game.is_collision(point_u)) or
            (dir_d and game.is_collision(point_d)),

            # Danger Right
            (dir_r and game.is_collision(point_d)) or
            (dir_l and game.is_collision(point_u)) or
            (dir_u and game.is_collision(point_r)) or
            (dir_d and game.is_collision(point_l)),

            # Danger Left
            (dir_r and game.is_collision(point_u)) or
            (dir_l and game.is_collision(point_d)) or
            (dir_u and game.is_collision(point_l)) or
            (dir_d and game.is_collision(point_r)),

            # Snake Direction (only one is TRUE)
            dir_l,
            dir_r,
            dir_u,
            dir_d,

            # Food Location
            game.food.x < game.head.x,  # Food Left
            game.food.x > game.head.x,  # Food Right
            game.food.y < game.head.y,  # Food Up
            game.food.y > game.head.y  # Food Down

        ]

        return np.array(state, dtype=int)

    def remember(self, state, action, reward, next_state, game_over):
        self.memory.append((state, action, reward, next_state, game_over))  # popleft if MAX_MEMORY is reached

    def train_long_memory(self):
        if len(self.memory) > BATCH_SIZE:
            mini_sample = random.sample(self.memory, BATCH_SIZE)  # list of tuples - see remember function
        else:
            mini_sample = self.memory

        # Need to un-bundle the list of tuples
        states, actions, rewards, next_states, game_overs = zip(*mini_sample)
        self.trainer.train_step(states, actions, rewards, next_states, game_overs)

    def train_short_memory(self, state, action, reward, next_state, game_over):
        self.trainer.train_step(state, action, reward, next_state, game_over)

    def get_action(self, state):
        # random moves: tradeoff exploration / exploitation
        self.epsilon = 80 - self.n_games  # TODO: Experiment with hard code 80
        final_move = [0, 0, 0]

        # Random Move - Reduces in frequency as n_games increases
        if random.randint(0, 200) < self.epsilon:
            move = random.randint(0, 2)  # 0, 1 or 2
            final_move[move] = 1
        # Learnt Move
        else:
            state0 = torch.tensor(state, dtype=torch.float)
            prediction = self.model(state0)

            move = torch.argmax(prediction).item()
            final_move[move] = 1

        return final_move


def train():
    plot_score = []
    plot_mean_score = []
    total_score = 0
    record = 0
    agent = Agent()
    game = SnakeGameAI()

    while True:
        # get old state
        state_old = agent.get_state(game)

        # get move
        final_move = agent.get_action(state_old)

        # perform move and get new state
        reward, game_over, score = game.play_step(final_move)
        state_new = agent.get_state(game)

        # train short memory (only for one step)
        agent.train_short_memory(state_old, final_move, reward, state_new, game_over)

        # remember
        agent.remember(state_old, final_move, reward, state_new, game_over)

        if game_over:
            # train the long memory (replay memory, experience replay)
            game.reset()
            agent.n_games += 1
            agent.train_long_memory()

            if score > record:
                record = score
                agent.model.save()

            # print('Game %d Score %d Record $d' % (agent.n_games, score, record))

            plot_score.append(score)
            total_score += score
            mean_score = total_score / agent.n_games
            plot_mean_score.append(mean_score)

            plot(plot_score, plot_mean_score)


if __name__ == '__main__':
    train()
