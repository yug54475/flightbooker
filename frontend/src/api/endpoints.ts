import { api } from './client';
import type {
  AuthResponse,
  SignupRequest,
  LoginRequest,
  User,
  UserPolicy,
  PolicyUpdateRequest,
  Itinerary,
  DisruptionEvent,
  SimulateDisruptionRequest,
  SimulateDisruptionResponse,
  AgentProposal,
  ApprovalRespondRequest,
  ApprovalRespondResponse,
  Notification,
  InsuranceClaim,
  TimelineEntry,
} from '../types';

// Auth
export const signup = (body: SignupRequest) =>
  api.post<AuthResponse>('/v1/auth/signup', body);

export const login = (body: LoginRequest) =>
  api.post<AuthResponse>('/v1/auth/login', body);

// User
export const getMe = (token: string) =>
  api.get<User>('/v1/users/me', token);

export const getPolicy = (token: string) =>
  api.get<UserPolicy>('/v1/users/me/policy', token);

export const updatePolicy = (body: PolicyUpdateRequest, token: string) =>
  api.patch<UserPolicy>('/v1/users/me/policy', body, token);

// Itineraries
export const getItineraries = (userId: string, token: string) =>
  api.get<Itinerary[]>(`/v1/itineraries/${userId}`, token);

// Disruptions
export const getDisruptions = (userId: string, token: string) =>
  api.get<DisruptionEvent[]>(`/v1/disruptions/${userId}`, token);

export const simulateDisruption = (
  body: SimulateDisruptionRequest,
  token: string,
) => api.post<SimulateDisruptionResponse>('/v1/disruptions/simulate', body, token);

// Agent proposals
export const getAgentProposal = (jobId: string, token: string) =>
  api.get<AgentProposal>(`/v1/agent-proposals/${jobId}`, token);

// Approvals
export const respondToApproval = (
  approvalId: string,
  body: ApprovalRespondRequest,
  token: string,
) =>
  api.post<ApprovalRespondResponse>(
    `/v1/approvals/${approvalId}/respond`,
    body,
    token,
  );

// Timeline
export const getTimeline = (userId: string, token: string) =>
  api.get<TimelineEntry[]>(`/v1/timeline/${userId}`, token);

// Notifications
export const getNotifications = (userId: string, token: string) =>
  api.get<Notification[]>(`/v1/notifications/${userId}`, token);

// Insurance claims
export const getInsuranceClaims = (userId: string, token: string) =>
  api.get<InsuranceClaim[]>(`/v1/insurance-claims/${userId}`, token);
