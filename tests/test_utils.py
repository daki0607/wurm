import unittest
import torch

from wurm import utils


class TestUtils(unittest.TestCase):
    def test_rotate_image_batch(self):
        n, c, h, w = 4, 1, 9, 9
        img = torch.zeros((n, c, h, w))

        img[0, :, 1, 1] = 1
        img[0, :, 2, 1] = 1
        img[1, :, 7, 1] = 1
        img[1, :, 7, 2] = 1
        img[2, :, 7, 7] = 1
        img[2, :, 6, 7] = 1
        img[3, :, 1, 7] = 1
        img[3, :, 1, 6] = 1

        i = 1
        rot = utils.rotate_image_batch(img, degree=90)
        self.assertTrue(torch.equal(img[0], rot[i]))

        i = 2
        rot = utils.rotate_image_batch(img, degree=180)
        self.assertTrue(torch.equal(img[0], rot[i]))

        i = 3
        rot = utils.rotate_image_batch(img, degree=270)
        self.assertTrue(torch.equal(img[0], rot[i]))

