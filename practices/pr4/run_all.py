import os

import a01_dirty_read
import a02_non_repeatable_read
import a03_phantom_read
import a04_lost_update

os.makedirs("results", exist_ok=True)

a01_dirty_read.demo()
print()
a02_non_repeatable_read.demo()
print()
a03_phantom_read.demo()
print()
a04_lost_update.demo()
