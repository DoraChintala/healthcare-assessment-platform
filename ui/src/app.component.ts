import { Component, OnDestroy } from '@angular/core';
import { CommonModule, CurrencyPipe, DatePipe, JsonPipe, KeyValuePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpErrorResponse, HttpHeaders } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

// ── Local demo user store (replaces raw token for login UX) ───────────────────
// In production this would be a real auth backend (OIDC / JWT).
// Token values map to the existing gateway demo tokens.
interface DemoUser {
  username: string;
  passwordHash: string; // stored as btoa(password) — demo only, not real hashing
  role: 'reviewer' | 'candidate';
  firstName: string;
  lastName: string;
  token: string;
}

// ── Domain interfaces ──────────────────────────────────────────────────────────
interface Rule     { id: string; status: string; reason: string; source: string; }
interface Evidence { source_id: string; quote: string; }
interface Policy   { id: string; version: string; text: string; }
interface RegistryEvidence {
  license_number: string; state: string; credential: string;
  status: string; expires_on: string; source: string;
}
interface WorkflowResult {
  candidate?: {
    years_experience: number | null;
    license_number: string | null;
    license_state: string | null;
    evidence: Record<string, Evidence>;
  };
  summary?:          { text: string; recommendation: string };
  rules?:            Rule[];
  policies?:         Policy[];
  registry_evidence?: RegistryEvidence | null;
  decision?:         { action: string; notes: string; reviewer: string };
  usage?: {
    provider?: string; input_tokens?: number; output_tokens?: number;
    estimated_model_cost_usd?: number; cost_configured?: boolean;
    call_latency_seconds?: number;
  };
}
interface Assessment {
  id: string; job_id: string; status: string; version: number;
  attempts: number; result: WorkflowResult | null;
  error: string | null; created_at: string;
}
interface Sample { label: string; resume_text: string; job_id: string; }
interface Job    { id: string; title: string; minimum_years: number; license_state: string; }
interface Audit  { action: string; actor: string; created_at: string; detail: unknown; }

// ─────────────────────────────────────────────────────────────────────────────
@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule, CurrencyPipe, DatePipe, JsonPipe, KeyValuePipe],
  templateUrl: './app.component.html',
})
export class AppComponent implements OnDestroy {

  // ── Auth / connection ──────────────────────────────────────────────────────
  // Landing screen: 'login' | 'signup'
  authScreen   = 'login';

  // Login form
  loginUsername = '';
  loginPassword = '';
  loginRole     = 'candidate' as 'reviewer' | 'candidate';

  // Sign-up form
  signupUsername  = '';
  signupPassword  = '';
  signupConfirm   = '';
  signupFirstName = '';
  signupLastName  = '';
  signupRole      = 'candidate' as 'reviewer' | 'candidate';
  signupError     = '';
  signupSuccess   = '';

  // Seeded demo accounts — password shown in UI hint
  private demoUsers: DemoUser[] = [
    {
      username: 'reviewer',
      passwordHash: btoa('Review@123'),
      role: 'reviewer',
      firstName: 'Alex',
      lastName: 'Morgan',
      token: 'local-demo-reviewer-token',
    },
    {
      username: 'nurse.sarah',
      passwordHash: btoa('Nurse@123'),
      role: 'candidate',
      firstName: 'Sarah',
      lastName: 'Johnson',
      token: 'local-demo-viewer-token',
    },
  ];

  token      = '';
  connected  = false;
  connecting = false;
  error      = '';

  // ── Navigation ─────────────────────────────────────────────────────────────
  view        = 'dashboard';   // 'dashboard' | 'profile' | 'jobs' | 'assessments'
  profileTab  = 'basic';       // 'basic' | 'credentials' | 'resume'

  // ── Profile form fields ────────────────────────────────────────────────────
  firstName        = '';
  lastName         = '';
  profileEmail     = '';
  profilePhone     = '';
  profileSpecialty = '';
  profileYears     = '';
  profileState     = '';
  profileLicense   = '';
  profileLicState  = '';
  certBLS          = '';
  certACLS         = '';
  profileComplete  = false;
  licenseVerified  = false;
  resumeUploaded   = false;

  // ── Jobs & samples ─────────────────────────────────────────────────────────
  jobs    : Job[]    = [];
  samples : Sample[] = [];
  jobId   = 'rn-icu';

  // ── Resume ─────────────────────────────────────────────────────────────────
  resume = '';

  // ── Assessments ────────────────────────────────────────────────────────────
  assessments : Assessment[] = [];
  selected    : Assessment | null = null;
  events      : Audit[] = [];
  busy        = false;
  refreshing  = false;

  // ── Review form ────────────────────────────────────────────────────────────
  notes             = '';
  correctionLicense = '';
  correctionState   = '';
  correctionYears   = '';

  private timer?       : ReturnType<typeof setInterval>;
  private submittedBody = '';
  private submissionKey = '';

  constructor(private http: HttpClient) {}

  // ── Computed helpers ───────────────────────────────────────────────────────

  get initials(): string {
    const f = this.firstName.trim();
    const l = this.lastName.trim();
    if (f && l) return (f[0] + l[0]).toUpperCase();
    if (f)      return f.slice(0, 2).toUpperCase();
    return 'ME';
  }

  get profilePct(): number {
    let score = 0;
    if (this.firstName && this.lastName)   score += 20;
    if (this.profileEmail)                 score += 10;
    if (this.profileSpecialty)             score += 15;
    if (this.profileYears)                 score += 10;
    if (this.profileLicense)               score += 15;
    if (this.profileLicState)              score += 10;
    if (this.resume.length >= 10)          score += 20;
    return score;
  }

  get pendingCount(): number {
    return this.assessments.filter(a =>
      a.status === 'AWAITING_APPROVAL' ||
      a.status === 'AWAITING_CLARIFICATION' ||
      a.status === 'QUEUED' ||
      a.status === 'PROCESSING'
    ).length;
  }

  get completedCount(): number {
    return this.assessments.filter(a => a.status === 'COMPLETED').length;
  }

  get hasCompletedAssessment(): boolean {
    return this.assessments.some(a => a.status === 'COMPLETED');
  }

  get bestMatch(): number {
    if (!this.jobs.length || !this.resumeUploaded) return 0;
    return Math.max(...this.jobs.map(j => this.matchScore(j)));
  }

  // ── Match scoring (client-side heuristic) ─────────────────────────────────
  // Scores are estimated from the resume text — the real authoritative
  // qualification check is done server-side by the rules engine.

  expScore(job: Job): number {
    const match = this.resume.match(/Experience:\s*(\d+(?:\.\d+)?)/i);
    if (!match) return 0;
    const yrs = parseFloat(match[1]);
    if (yrs >= job.minimum_years * 1.5) return 100;
    if (yrs >= job.minimum_years)       return 85;
    if (yrs >= job.minimum_years * .75) return 50;
    return 20;
  }

  stateScore(job: Job): number {
    const match = this.resume.match(/State:\s*([A-Z]{2})/i);
    if (!match) return 0;
    return match[1].toUpperCase() === job.license_state.toUpperCase() ? 100 : 10;
  }

  licScore(): number {
    const match = this.resume.match(/License:\s*([A-Za-z0-9-]+)/i);
    if (!match) return 0;
    const lic = match[1].toUpperCase();
    // Has value and matches expected format
    return lic.length >= 4 ? 90 : 40;
  }

  resumeScore(): number {
    const len = this.resume.trim().length;
    if (len === 0)    return 0;
    if (len < 50)     return 20;
    if (len < 200)    return 55;
    if (len < 500)    return 80;
    return 95;
  }

  matchScore(job: Job): number {
    if (!this.resumeUploaded) return 0;
    const avg = (
      this.expScore(job) * .35 +
      this.stateScore(job) * .25 +
      this.licScore() * .25 +
      this.resumeScore() * .15
    );
    return Math.round(avg);
  }

  scoreClass(score: number): string {
    if (score >= 75) return 'high';
    if (score >= 45) return 'med';
    return 'low';
  }

  jobLabel(jobId: string): string {
    return this.jobs.find(j => j.id === jobId)?.title ?? jobId;
  }

  badgeClass(status: string): string {
    const s = status.toLowerCase();
    if (s === 'completed')                                           return 'pass completed';
    if (s === 'failed')                                              return 'fail failed';
    if (s === 'awaiting_approval' || s === 'awaiting_clarification') return 'unknown awaiting';
    if (s === 'queued' || s === 'processing')                        return 'processing queued';
    return '';
  }

  human(value: string): string {
    return value.replace(/_/g, ' ').toLowerCase();
  }

  // ── Auth ───────────────────────────────────────────────────────────────────

  headers(extra: Record<string, string> = {}): HttpHeaders {
    return new HttpHeaders({ Authorization: 'Bearer ' + this.token, ...extra });
  }

  message(err: unknown): void {
    if (err instanceof HttpErrorResponse) {
      this.error = typeof err.error?.detail === 'string'
        ? err.error.detail
        : `Request failed (${err.status || 'connection unavailable'}). Check credentials and service health.`;
    } else {
      this.error = 'Request failed. Refresh and try again.';
    }
  }

  // Validate username/password against local demo store, then hit the API
  async login(): Promise<void> {
    this.error = '';
    if (!this.loginUsername.trim() || !this.loginPassword.trim()) {
      this.error = 'Please enter your username and password.';
      return;
    }
    const user = this.demoUsers.find(
      u => u.username.toLowerCase() === this.loginUsername.trim().toLowerCase()
        && u.passwordHash === btoa(this.loginPassword)
        && u.role === this.loginRole
    );
    if (!user) {
      this.error = 'Invalid username or password. Check the demo credentials below.';
      return;
    }
    // Pre-fill profile fields from user record
    this.firstName = user.firstName;
    this.lastName  = user.lastName;
    this.token     = user.token;
    await this.connect();
  }

  // Register a new demo account (stored in memory for session lifetime)
  register(): void {
    this.signupError   = '';
    this.signupSuccess = '';
    if (!this.signupFirstName || !this.signupLastName) {
      this.signupError = 'First and last name are required.'; return;
    }
    if (!this.signupUsername.trim()) {
      this.signupError = 'Username is required.'; return;
    }
    if (this.demoUsers.some(u => u.username.toLowerCase() === this.signupUsername.toLowerCase())) {
      this.signupError = 'Username already taken. Try another.'; return;
    }
    if (this.signupPassword.length < 6) {
      this.signupError = 'Password must be at least 6 characters.'; return;
    }
    if (this.signupPassword !== this.signupConfirm) {
      this.signupError = 'Passwords do not match.'; return;
    }
    // New candidates get viewer token; new reviewers get reviewer token
    const newUser: DemoUser = {
      username:     this.signupUsername.trim(),
      passwordHash: btoa(this.signupPassword),
      role:         this.signupRole,
      firstName:    this.signupFirstName.trim(),
      lastName:     this.signupLastName.trim(),
      token: this.signupRole === 'reviewer'
        ? 'local-demo-reviewer-token'
        : 'local-demo-viewer-token',
    };
    this.demoUsers.push(newUser);
    this.signupSuccess = `Account created! You can now sign in as ${newUser.username}.`;
    // Auto-switch to login and pre-fill
    setTimeout(() => {
      this.loginUsername = newUser.username;
      this.loginRole     = newUser.role;
      this.authScreen    = 'login';
      this.signupSuccess = '';
    }, 1800);
  }

  async connect(): Promise<void> {
    this.connecting = true; this.error = '';
    try {
      this.jobs    = await firstValueFrom(this.http.get<Job[]>   ('/api/jobs',    { headers: this.headers() }));
      this.samples = await firstValueFrom(this.http.get<Sample[]>('/api/samples', { headers: this.headers() }));
      this.connected = true;
      if (!this.resume && this.samples.length) this.loadSample('0');
      await this.refresh();
      if (this.timer) clearInterval(this.timer);
      this.timer = setInterval(() => void this.refresh(), 2000);
      this.view = 'dashboard';
    } catch (err) {
      this.message(err);
    } finally {
      this.connecting = false;
    }
  }

  disconnect(): void {
    if (this.timer) clearInterval(this.timer);
    this.connected    = false;
    this.assessments  = [];
    this.selected     = null;
    this.events       = [];
    this.error        = '';
    this.token        = '';
    this.loginPassword = '';
    this.view         = 'dashboard';
    this.authScreen   = 'login';
  }

  // ── Profile actions ────────────────────────────────────────────────────────

  saveProfile(): void {
    if (this.firstName && this.lastName && this.profileSpecialty) {
      this.profileComplete = true;
      this.error = '';
      this.profileTab = 'credentials';
    } else {
      this.error = 'Please fill in first name, last name, and specialty.';
    }
  }

  saveCredentials(): void {
    if (this.profileLicense && this.profileLicState) {
      this.licenseVerified = true;
      this.error = '';
      this.profileTab = 'resume';
    } else {
      this.error = 'Please enter your license number and issuing state.';
    }
  }

  saveResume(): void {
    if (this.resume.length >= 10) {
      this.resumeUploaded = true;
      this.error = '';
      // Auto-populate license & state in profile if not already set
      const licMatch   = this.resume.match(/License:\s*([A-Za-z0-9-]+)/i);
      const stateMatch = this.resume.match(/State:\s*([A-Z]{2})/i);
      if (licMatch   && !this.profileLicense)   this.profileLicense  = licMatch[1].toUpperCase();
      if (stateMatch && !this.profileLicState)  this.profileLicState = stateMatch[1].toUpperCase();
      this.view = 'jobs';
    }
  }

  triggerResumeUpload(): void {
    // File picker UX hint — in production wire to a real <input type="file">
    // For now, just focus the textarea so the user can paste
    const el = document.getElementById('resumeText');
    if (el) el.focus();
  }

  get profileName(): string {
    return [this.firstName, this.lastName].filter(Boolean).join(' ');
  }

  // ── Sample loading ─────────────────────────────────────────────────────────

  loadSample(index: string): void {
    const sample = this.samples[Number(index)];
    if (sample) {
      this.resume  = sample.resume_text;
      this.jobId   = sample.job_id;
      this.resumeUploaded = true;
    }
  }

  // ── Refresh ────────────────────────────────────────────────────────────────

  async refresh(): Promise<void> {
    if (!this.connected || this.refreshing) return;
    this.refreshing = true;
    try {
      this.assessments = await firstValueFrom(
        this.http.get<Assessment[]>('/api/assessments', { headers: this.headers() })
      );
      if (this.selected) {
        this.selected = this.assessments.find(x => x.id === this.selected!.id) ?? this.selected;
      }
    } catch (err) {
      this.message(err);
    } finally {
      this.refreshing = false;
    }
  }

  // ── Assessment submission ──────────────────────────────────────────────────

  async submitAssessment(): Promise<void> {
    if (this.resume.length < 10) {
      this.error = 'Add resume text in Profile → Resume before submitting.';
      return;
    }
    this.busy = true; this.error = '';
    const body = { resume_text: this.resume, job_id: this.jobId };
    const encoded = JSON.stringify(body);
    if (encoded !== this.submittedBody) {
      this.submittedBody = encoded;
      this.submissionKey = crypto.randomUUID();
    }
    try {
      this.selected = await firstValueFrom(
        this.http.post<Assessment>('/api/assessments', body, {
          headers: this.headers({ 'Idempotency-Key': this.submissionKey }),
        })
      );
      this.events = [];
      await this.refresh();
      this.view = 'assessments';
    } catch (err) {
      this.message(err);
    } finally {
      this.busy = false;
    }
  }

  // ── Select assessment ──────────────────────────────────────────────────────

  async select(row: Assessment): Promise<void> {
    this.selected         = row;
    this.notes            = '';
    this.correctionLicense = '';
    this.correctionYears  = '';
    this.correctionState  = '';
    this.events           = [];
    await this.loadAudit();
  }

  async selectAndGo(row: Assessment): Promise<void> {
    await this.select(row);
    this.view = 'assessments';
  }

  async loadAudit(): Promise<void> {
    if (!this.selected) return;
    try {
      this.events = await firstValueFrom(
        this.http.get<Audit[]>(`/api/assessments/${this.selected.id}/audit`, { headers: this.headers() })
      );
    } catch (err) {
      this.message(err);
    }
  }

  // ── Review / clarify / approve ─────────────────────────────────────────────

  async review(action: 'clarify' | 'approve' | 'reject'): Promise<void> {
    if (!this.selected) return;
    this.busy = true; this.error = '';
    const corrections: Record<string, string | number> = {};
    if (action === 'clarify') {
      if (this.correctionLicense.trim()) corrections['license_number'] = this.correctionLicense.trim().toUpperCase();
      if (this.correctionState.trim())   corrections['license_state']  = this.correctionState.trim().toUpperCase();
      if (this.correctionYears.trim())   corrections['years_experience'] = Number(this.correctionYears);
    }
    try {
      this.selected = await firstValueFrom(
        this.http.post<Assessment>(
          `/api/assessments/${this.selected.id}/review`,
          { action, notes: this.notes, corrections, expected_version: this.selected.version },
          { headers: this.headers() }
        )
      );
      this.notes = '';
      await this.refresh();
      await this.loadAudit();
    } catch (err) {
      this.message(err);
      await this.refresh();
    } finally {
      this.busy = false;
    }
  }

  ngOnDestroy(): void {
    if (this.timer) clearInterval(this.timer);
  }
}
