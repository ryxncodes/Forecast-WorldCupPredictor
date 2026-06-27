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

export type SyncStatus = {
  checked_at: string | null;
  status: string;
  forecast_changed: boolean;
  result_changed: boolean;
  completed_matches: number;
};

export type Dashboard = {
  forecast: Forecast;
  standings: Standings;
  sync_status: SyncStatus;
};

export type BracketTeam = {
  team_id: number;
  team: string;
  group: string;
  champion_probability: number;
  final_probability: number;
  semifinal_probability: number;
};

export type BracketMatch = {
  match_number: number;
  round: string;
  home: BracketTeam;
  away: BracketTeam;
  home_slot?: string;
  away_slot?: string;
  home_source?: number;
  away_source?: number;
  home_expected_goals: number;
  away_expected_goals: number;
  home_advance_probability: number;
  away_advance_probability: number;
  projected_winner: BracketTeam;
};

export type BracketRound = {
  key: string;
  label: string;
  matches: BracketMatch[];
};

export type BracketProjection = {
  forecast: {
    id: number;
    created_at: string;
    completed_results: number;
    simulations: number;
  };
  favorite: BracketTeam;
  finalists: BracketTeam[];
  rounds: BracketRound[];
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
  matchup_status?: "confirmed" | "projected";
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
  model_mode: string;
};

export type AccuracyMatch = {
  match_id: number;
  match_number: number;
  kickoff: string;
  group: string;
  home_team: string;
  away_team: string;
  home_team_rating: number;
  away_team_rating: number;
  home_score: number;
  away_score: number;
  home_expected_goals: number;
  away_expected_goals: number;
  home_win_probability: number;
  draw_probability: number;
  away_win_probability: number;
  predicted_outcome: "home" | "draw" | "away";
  stored_predicted_outcome: "home" | "draw" | "away";
  predicted_outcome_label: string;
  actual_outcome: "home" | "draw" | "away";
  actual_outcome_label: string;
  picked_correct: boolean;
  stored_pick_matches_argmax: boolean;
  predicted_home_score: number;
  predicted_away_score: number;
  predicted_score_probability: number;
  prediction_source: "locked" | "backfilled";
  exact_score: boolean;
  brier_score: number;
  log_loss: number;
  goal_error: number;
};

export type OutcomeDistribution = {
  home: number;
  draw: number;
  away: number;
};

export type AccuracyReport = {
  completed_matches: number;
  scored_matches: number;
  unscored_completed_matches: number;
  locked_predictions: number;
  backfilled_predictions: number;
  picked_correct: number;
  pick_accuracy: number;
  exact_scores: number;
  exact_score_rate: number;
  average_brier_score: number;
  average_log_loss: number;
  average_goal_error: number;
  predicted_result_distribution: OutcomeDistribution;
  actual_result_distribution: OutcomeDistribution;
  matches: AccuracyMatch[];
};
