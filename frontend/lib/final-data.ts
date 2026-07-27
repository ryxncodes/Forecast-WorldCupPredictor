import dashboardSnapshot from "../data/final/dashboard.json";
import bracketSnapshot from "../data/final/bracket.json";
import matchesSnapshot from "../data/final/matches.json";
import accuracySnapshot from "../data/final/accuracy.json";
import historySnapshot from "../data/final/history.json";
import type { AccuracyReport, BracketProjection, Dashboard, Forecast, Match } from "./types";

export const finalDashboard = dashboardSnapshot as unknown as Dashboard;
export const finalBracket = bracketSnapshot as unknown as BracketProjection;
export const finalMatches = matchesSnapshot as unknown as Match[];
export const finalAccuracy = accuracySnapshot as unknown as AccuracyReport;
export const finalHistory = historySnapshot as unknown as Forecast[];
