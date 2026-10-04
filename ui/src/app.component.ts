import { Component, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpErrorResponse, HttpHeaders } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

interface Rule {id: string; status: string; reason: string; source: string;}
interface Evidence {source_id: string; quote: string;}
interface Policy {id: string; version: string; text: string;}
interface WorkflowResult {
  candidate?: {years_experience: number | null; license_number: string | null; license_state: string | null; evidence: Record<string,Evidence>};
  summary?: {text: string; recommendation: string};
  rules?: Rule[]; policies?: Policy[];
  usage?: {provider?: string; input_tokens?: number; output_tokens?: number; estimated_model_cost_usd?: number; cost_configured?: boolean; call_latency_seconds?: number};
  decision?: {action: string; notes: string; reviewer: string};
}
interface Assessment {id: string; job_id: string; status: string; version: number; attempts: number; result: WorkflowResult | null; error: string | null; created_at: string;}
interface Sample {label: string; resume_text: string; job_id: string;}
interface Job {id: string; title: string; minimum_years: number; license_state: string;}
interface Audit {action: string; actor: string; created_at: string; detail: unknown;}

@Component({selector: 'app-root', standalone: true, imports: [CommonModule,FormsModule], templateUrl: './app.component.html'})
export class AppComponent implements OnDestroy {
  token = 'local-demo-reviewer-token';
  connected = false;
  connecting = false;
  busy = false;
  refreshing = false;
  error = '';
  jobs: Job[] = [];
  samples: Sample[] = [];
  assessments: Assessment[] = [];
  selected: Assessment | null = null;
  events: Audit[] = [];
  jobId = 'rn-icu';
  resume = '';
  notes = '';
  correctionLicense = '';
  correctionState = '';
  correctionYears = '';
  private timer?: ReturnType<typeof setInterval>;
  private submittedBody = '';
  private submissionKey = '';
  constructor(private http: HttpClient) {}
  headers(extra: Record<string,string> = {}): HttpHeaders {return new HttpHeaders({'Authorization': 'Bearer '+this.token, ...extra});}
  message(err: unknown) {
    if (err instanceof HttpErrorResponse) {
      this.error = typeof err.error?.detail === 'string' ? err.error.detail : `Request failed (${err.status || 'connection unavailable'}). Check the token and service health.`;
    } else {this.error = 'Request failed. Refresh and try again.';}
  }
  async connect() {
    this.connecting = true; this.error = '';
    try {
      this.jobs = await firstValueFrom(this.http.get<Job[]>('/api/jobs',{headers:this.headers()}));
      this.samples = await firstValueFrom(this.http.get<Sample[]>('/api/samples',{headers:this.headers()}));
      this.connected = true;
      if (!this.resume && this.samples.length) this.loadSample('0');
      await this.refresh();
      if (this.timer) clearInterval(this.timer);
      this.timer = setInterval(()=>void this.refresh(),2000);
    } catch(err) {this.message(err);} finally {this.connecting=false;}
  }
  loadSample(index: string) {
    const sample=this.samples[Number(index)];
    if (sample) {this.resume=sample.resume_text;this.jobId=sample.job_id;}
  }
  async refresh() {
    if (!this.connected || this.refreshing) return;
    this.refreshing=true;
    try {
      this.assessments=await firstValueFrom(this.http.get<Assessment[]>('/api/assessments',{headers:this.headers()}));
      if (this.selected) {
        this.selected=this.assessments.find(x=>x.id===this.selected!.id)||this.selected;
      }
    } catch(err) {this.message(err);} finally {this.refreshing=false;}
  }
  async submit() {
    this.busy=true;this.error='';
    const body={resume_text:this.resume,job_id:this.jobId};
    const encoded=JSON.stringify(body);
    if (encoded!==this.submittedBody) {this.submittedBody=encoded;this.submissionKey=crypto.randomUUID();}
    try {
      this.selected=await firstValueFrom(this.http.post<Assessment>('/api/assessments',body,{headers:this.headers({'Idempotency-Key':this.submissionKey})}));
      this.events=[];
      await this.refresh();
    } catch(err) {this.message(err);} finally {this.busy=false;}
  }
  async select(row: Assessment) {
    this.selected=row;this.notes='';this.correctionLicense='';this.correctionYears='';this.correctionState='';this.events=[];
    await this.loadAudit();
  }
  async loadAudit() {
    if (!this.selected) return;
    try {this.events=await firstValueFrom(this.http.get<Audit[]>(`/api/assessments/${this.selected.id}/audit`,{headers:this.headers()}));}
    catch(err) {this.message(err);}
  }
  async review(action: 'clarify' | 'approve' | 'reject') {
    if (!this.selected) return;
    this.busy=true;this.error='';
    const corrections: Record<string,string|number>={};
    if (action==='clarify') {
      if (this.correctionLicense.trim()) corrections['license_number']=this.correctionLicense.trim().toUpperCase();
      if (this.correctionState.trim()) corrections['license_state']=this.correctionState.trim().toUpperCase();
      if (this.correctionYears.trim()) corrections['years_experience']=Number(this.correctionYears);
    }
    try {
      this.selected=await firstValueFrom(this.http.post<Assessment>(`/api/assessments/${this.selected.id}/review`,{action,notes:this.notes,corrections,expected_version:this.selected.version},{headers:this.headers()}));
      this.notes=''; await this.refresh(); await this.loadAudit();
    } catch(err) {this.message(err);await this.refresh();} finally {this.busy=false;}
  }
  human(value: string) {return value.replaceAll('_',' ').toLowerCase();}
  ngOnDestroy() {if (this.timer) clearInterval(this.timer);}
}
