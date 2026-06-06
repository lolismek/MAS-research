import random
from collections import defaultdict

def simulate_game(iterations=100000):
    balls_range = range(1, 101)
    ball_ejection_count = defaultdict(int)

    for _ in range(iterations):
        ramp = list(balls_range)
        platform = ramp[:3]
        del ramp[:3]

        while platform:
            # Randomly choose a piston to fire (1, 2, or 3 corresponding to the index 0, 1, 2)
            fired_piston = random.choice([0, 1, 2])
            ejected_ball = platform.pop(fired_piston)
            ball_ejection_count[ejected_ball] += 1

            # Move balls according to rules
            if fired_piston == 0:
                # Nothing changes, just remove ball 0, advance one ball
                if ramp:
                    platform.append(ramp.pop(0))
            elif fired_piston == 1:
                # Ball at position 2 moves to position 0
                if len(platform) >= 2:
                    platform = [platform[1]] + platform[:1]
                if ramp:
                    platform.extend(ramp[:2])
                    del ramp[:2]
            elif fired_piston == 2:
                # Ball at position 1 moves to position 0, and fill position 1 and 2
                if len(platform) >= 1:
                    platform = [platform[0]]
                if ramp:
                    next_balls = ramp[:2]
                    platform.extend(next_balls)
                    del ramp[:2]

    # Calculate probabilities of ejection
    probabilities = {ball: count / iterations for ball, count in ball_ejection_count.items()}
    
    # Find the ball with the highest ejection probability
    best_ball = max(probabilities, key=probabilities.get)
    
    return best_ball, probabilities[best_ball]

best_ball, best_probability = simulate_game()
print(f"The best ball to pick is: {best_ball} with an ejection probability of: {best_probability:.4f}")
