export type ProbabilityKey =
  | "advance_probability"
  | "win_group_probability"
  | "runner_up_probability"
  | "best_third_probability"
  | "round_of_32_probability"
  | "round_of_16_probability"
  | "quarterfinal_probability"
  | "semifinal_probability"
  | "final_probability"
  | "champion_probability";

export type ForecastRow = {
  team_id: number;
  team: string;
  group: string;
  advance_probability: number;
  win_group_probability: number;
  runner_up_probability: number;
  best_third_probability: number;
  round_of_32_probability: number;
  round_of_16_probability: number;
  quarterfinal_probability: number;
  semifinal_probability: number;
  final_probability: number;
  champion_probability: number;
};

export type Forecast = {
  id: number;
  created_at: string;
  simulations: number;
  label: string;
  completed_results: number;
  data_as_of: string | null;
  data_source: string;
  model_version: string;
  probabilities: ForecastRow[];
};

export type Standing = {
  team_id: number;
  team: string;
  group: string;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  points: number;
};

export type Standings = {
  groups: Record<string, Standing[]>;
  best_third: Standing[];
};

export type Match = {
  id: number;
  match_number: number;
  group: string;
  stage: string;
  kickoff: string;
  venue: string;
  home_team_id: number;
  home_team: string;
  away_team_id: number;
  away_team: string;
  home_score: number | null;
  away_score: number | null;
  completed: boolean;
  status: "pre" | "in" | "post";
  status_detail: string;
  source: string;
  details: MatchDetails;
  prediction: MatchPrediction;
};

export type MatchTimelineEvent = {
  type: string;
  minute: string;
  team: string;
  player: string;
  scoring_play: boolean;
  penalty: boolean;
  own_goal: boolean;
  yellow_card: boolean;
  red_card: boolean;
};

export type MatchDetails = {
  venue_full_name?: string;
  venue_city?: string;
  venue_country?: string;
  attendance?: number | null;
  broadcasts?: string[];
  goals?: MatchTimelineEvent[];
  events?: MatchTimelineEvent[];
};

export type MatchPrediction = {
  home_win_probability: number;
  draw_probability: number;
  away_win_probability: number;
  home_expected_goals: number;
  away_expected_goals: number;
};
