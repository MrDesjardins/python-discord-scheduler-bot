
from enum import Enum


class TeamAlgo(Enum):
  WIN_RATIO = "win_ratio"
  K_D_RATIO = "k_d_ratio"
  CURRENT_MMR = "current_mmr"
  MAX_MMR = "max_mmr"
  
class MapAlgo(Enum):
  RANDOM = "random"
  WORSE_MAPS_FIRST = "worse_maps_first"
  BEST_MAPS_FIRST = "best_maps_first"
  LEAST_PLAYED = "least_played"