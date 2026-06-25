import json
from pathlib import Path


_PATH = Path(__file__).resolve().parents[2] / "data" / "model_parameters.json"
PARAMETERS = json.loads(_PATH.read_text())

MODEL_VERSION = PARAMETERS["version"]
RATING_K_FACTOR = float(PARAMETERS["rating_k_factor"])
RATING_MARGIN_EXPONENT = float(PARAMETERS["rating_margin_exponent"])
GOAL_BASE_RATE = float(PARAMETERS["goal_base_rate"])
GOAL_ELO_COEFFICIENT = float(PARAMETERS["goal_elo_coefficient"])
GOAL_RATE_FLOOR = float(PARAMETERS["goal_rate_floor"])
GOAL_RATE_CEILING = float(PARAMETERS["goal_rate_ceiling"])
