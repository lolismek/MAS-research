'''
Utility functions for collision detection and random gap generation.
'''
import random
def check_collision(bird, pipe):
    if bird.y - bird.radius < pipe.gap_y or bird.y + bird.radius > pipe.gap_y + pipe.gap_height:
        if pipe.x < bird.x < pipe.x + pipe.width:
            return True
    return False
def generate_random_gap(score):
    base_gap = 150
    difficulty_increase = score // 10
    min_gap_size = 100
    return max(random.randint(100, 400 - difficulty_increase), min_gap_size)