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
            # Randomly choose a piston to fire based on available balls
            fired_piston = random.choice(range(len(platform)))
            ejected_ball = platform.pop(fired_piston)
            ball_ejection_count[ejected_ball] += 1

            # Move balls according to rules
            if fired_piston == 0 and ramp:
                # Advance one ball to the empty spot
                platform.append(ramp.pop(0))
            elif fired_piston == 1:
                # Rearrange and fill from the ramp
                if len(platform) >= 1:
                    platform = [platform[0]]
                if ramp:
                    next_balls = ramp[:2]
                    platform.extend(next_balls)
                    del ramp[:2]
            elif fired_piston == 2:
                # Special case ensures valid moves; this isn't usually triggered due to prior conditions
                if ramp:
                    platform.append(ramp.pop(0))

    # Calculate probabilities of ejection
    probabilities = {ball: count / iterations for ball, count in ball_ejection_count.items()}
    
    # Find the ball with the highest ejection probability
    best_ball = max(probabilities, key=probabilities.get)
    
    return best_ball, probabilities[best_ball]

best_ball, best_probability = simulate_game()
print(f"The best ball to pick is: {best_ball} with an ejection probability of: {best_probability:.4f}")
