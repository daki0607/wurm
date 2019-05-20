import unittest
import pytest
import torch
from time import sleep, time

from wurm.envs import MultiSnake
from wurm.utils import head, body, food
from config import DEFAULT_DEVICE


print_envs = False
render_envs = True
render_sleep = 0.5
size = 12


def get_test_env(num_envs=1):
    env = MultiSnake(num_envs=num_envs, num_snakes=2, size=size, manual_setup=True)

    # Snake 1
    env.envs[:, 1, 5, 5] = 1
    env.envs[:, 2, 5, 5] = 4
    env.envs[:, 2, 4, 5] = 3
    env.envs[:, 2, 4, 4] = 2
    env.envs[:, 2, 4, 3] = 1
    # Snake 2
    env.envs[:, 3, 8, 7] = 1
    env.envs[:, 4, 8, 7] = 4
    env.envs[:, 4, 8, 8] = 3
    env.envs[:, 4, 8, 9] = 2
    env.envs[:, 4, 9, 9] = 1

    return env


def print_or_render(env):
    if print_envs:
        print('='*30)
        print(env._bodies)

    if render_envs:
        env.render()
        sleep(render_sleep)


class TestMultiSnakeEnv(unittest.TestCase):
    def test_random_actions(self):
        num_envs = 100
        num_steps = 100
        # Create some environments and run random actions for N steps, checking for consistency at each step
        env = MultiSnake(num_envs=num_envs, num_snakes=2, size=size, manual_setup=False)
        env.check_consistency()

        all_actions = {
            'agent_0': torch.randint(4, size=(num_steps, num_envs)).long().to(DEFAULT_DEVICE),
            'agent_1': torch.randint(4, size=(num_steps, num_envs)).long().to(DEFAULT_DEVICE),
        }

        t0 = time()
        for i in range(all_actions['agent_0'].shape[0]):
            actions = {
                agent: agent_actions[i] for agent, agent_actions in all_actions.items()
            }
            observations, reward, done, info = env.step(actions)
            env.reset(done['__all__'])
            env.check_consistency()

        t = time() - t0
        print(f'Ran {num_envs * num_steps} actions in {t}s = {num_envs * num_steps / t} actions/s')

    def test_basic_movement(self):
        env = get_test_env()

        # Add food
        env.envs[0, 0, 1, 1] = 1

        all_actions = {
            'agent_0': torch.Tensor([1, 2, 1, 1, 0, 3]).unsqueeze(1).long().to(DEFAULT_DEVICE),
            'agent_1': torch.Tensor([0, 1, 3, 2, 1, 0]).unsqueeze(1).long().to(DEFAULT_DEVICE),
        }
        expected_head_positions = [
            torch.Tensor([
                [5, 4],
                [4, 4],
                [4, 3],
                [4, 2],
                [5, 2],
                [5, 3]
            ]),
            torch.Tensor([
                [9, 7],
                [9, 6],
                [9, 5],
                [8, 5],
                [8, 4],
                [9, 4]
            ]),
        ]

        print_or_render(env)

        for i in range(all_actions['agent_0'].shape[0]):
            actions = {
                agent: agent_actions[i] for agent, agent_actions in all_actions.items()
            }

            observations, rewards, dones, info = env.step(actions)
            env.check_consistency()

            for i_agent in range(env.num_snakes):
                head_channel = env.head_channels[i_agent]
                body_channel = env.body_channels[i_agent]
                _env = env.envs[:, [0, head_channel, body_channel], :, :]

                head_position = torch.Tensor([
                    head(_env)[0, 0].flatten().argmax() // size, head(_env)[0, 0].flatten().argmax() % size
                ])
                self.assertTrue(torch.equal(head_position, expected_head_positions[i_agent][i]))
                # print(i_agent, head_position)

            print_or_render(env)

            if any(done for agent, done in dones.items()):
                # These actions shouldn't cause any deaths
                assert False

    def test_self_collision(self):
        env = get_test_env()

        # Add food so agent_0 eats it and grows
        env.envs[0, 0, 4, 3] = 1

        all_actions = {
            'agent_0': torch.Tensor([1, 2, 1, 1, 0, 3, 2, 0]).unsqueeze(1).long().to(DEFAULT_DEVICE),
            'agent_1': torch.Tensor([0, 1, 3, 2, 1, 0, 0, 1]).unsqueeze(1).long().to(DEFAULT_DEVICE),
        }

        print_or_render(env)

        for i in range(all_actions['agent_0'].shape[0]):
            actions = {
                agent: agent_actions[i] for agent, agent_actions in all_actions.items()
            }

            observations, rewards, dones, info = env.step(actions)
            env.check_consistency()

            print_or_render(env)

            if i >= 6:
                self.assertEqual(dones['agent_0'].item(), 1)
            else:
                self.assertEqual(dones['agent_0'].item(), 0)

        # Check some food has been created on death
        self.assertGreaterEqual(env.envs[:, 0].sum(), 2)

    def test_other_snake_collision(self):
        # Actions and snakes are arranged so agent_1 collides with agent_0 and dies
        env = get_test_env()
        env.envs[0, 0, 1, 1] = 1

        all_actions = {
            'agent_0': torch.Tensor([1, 2, 3, 3, 3, 3, 3, 2]).unsqueeze(1).long().to(DEFAULT_DEVICE),
            'agent_1': torch.Tensor([0, 1, 2, 2, 2, 2, 2, 2]).unsqueeze(1).long().to(DEFAULT_DEVICE),
        }

        print_or_render(env)

        for i in range(all_actions['agent_0'].shape[0]):
            actions = {
                agent: agent_actions[i] for agent, agent_actions in all_actions.items()
            }

            observations, rewards, dones, info = env.step(actions)
            env.check_consistency()

            if i >= 6:
                self.assertEqual(dones['agent_1'].item(), 1)
            else:
                self.assertEqual(dones['agent_1'].item(), 0)

            print_or_render(env)

        # Check some food has been created on death
        self.assertGreaterEqual(env.envs[:, 0].sum(), 2)

    def test_eat_food(self):
        env = get_test_env()

        # Add food
        env.envs[0, 0, 9, 7] = 1

        all_actions = {
            'agent_0': torch.Tensor([1, 2, 1, 1, 0, 3]).unsqueeze(1).long().to(DEFAULT_DEVICE),
            'agent_1': torch.Tensor([0, 1, 3, 2, 1, 0]).unsqueeze(1).long().to(DEFAULT_DEVICE),
        }

        print()
        if print_envs:
            print(env._bodies)

        if render_envs:
            env.render()
            sleep(render_sleep)

        for i in range(6):
            actions = {
                agent: agent_actions[i] for agent, agent_actions in all_actions.items()
            }

            observations, rewards, dones, info = env.step(actions)
            env.check_consistency()

            if print_envs:
                print('=' * 10)
                print(env._bodies)
                print('DONES:')
                print(dones)
                print()

            # Check reward given when expected
            if i == 0:
                self.assertEqual(rewards['agent_1'].item(), 1)

            if render_envs:
                env.render()
                sleep(render_sleep)

            if any(done for agent, done in dones.items()):
                # These actions shouldn't cause any deaths
                assert False

        # Check snake sizes. Expect agent_1: 4, agent_2: 5
        snake_sizes = env._bodies.view(1, 2, -1).max(dim=2)[0]
        self.assertTrue(torch.equal(snake_sizes, torch.Tensor([[4, 5]]).to(DEFAULT_DEVICE)))

        # Check food has been removed
        self.assertEqual(env.envs[0, 0, 9, 7].item(), 0)

        # Check new food has been created
        self.assertEqual(food(env.envs).sum().item(), 1)

    def test_create_envs(self):
        # Create a large number of environments and check consistency
        env = MultiSnake(num_envs=512, num_snakes=2, size=size, manual_setup=False)
        env.check_consistency()

    def test_reset(self):
        num_snakes = 2

        # agent_1 dies by other-collision, agent_0 dies by edge-collision
        env = get_test_env(num_envs=1)
        env.envs[:, 0, 1, 1] = 1

        all_actions = {
            'agent_0': torch.Tensor([1, 2, 3, 3, 3, 3, 3, 3, 3]).unsqueeze(1).long().to(DEFAULT_DEVICE),
            'agent_1': torch.Tensor([0, 1, 2, 2, 2, 2, 2, 2, 2]).unsqueeze(1).long().to(DEFAULT_DEVICE),
        }

        print_or_render(env)

        for i in range(all_actions['agent_0'].shape[0]):
            actions = {
                agent: agent_actions[i] for agent, agent_actions in all_actions.items()
            }

            observations, rewards, dones, info = env.step(actions)

            env.reset(dones['__all__'])

            print(i, dones)
            env.check_consistency()

            print_or_render(env)

        # Both snakes should've died and hence the environment should've reset
        self.assertTrue(torch.all(env._bodies.view(1, num_snakes, -1).max(dim=-1)[0] == env.initial_snake_length))

    def test_agent_observations(self):
        # Test that own snake appears green, others appear blue
        pass
