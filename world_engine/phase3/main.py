# main.py
import threading
from room_simulator import RoomSimulator
from config import NUM_BUILDINGS, NUM_FLOORS, NUM_ROOMS

def launch_room(b, f, r):
    building = f"b{b:02d}"
    floor    = f"f{f:02d}"
    room     = f"r{r:03d}"
    sim = RoomSimulator(building, floor, room)
    sim.run()

threads = []
for b in range(1, NUM_BUILDINGS + 1):
    for f in range(1, NUM_FLOORS + 1):
        for r in range(1, NUM_ROOMS + 1):
            t = threading.Thread(
                target=launch_room,
                args=(b, f, r),
                daemon=True
            )
            t.start()
            threads.append(t)

print(f"[MAIN] Launched {len(threads)} room simulators")

# خلّي الـ main thread شغال
for t in threads:
    t.join()
