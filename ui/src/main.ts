import { bootstrapApplication } from '@angular/platform-browser';
import { provideHttpClient } from '@angular/common/http';
import { AppComponent } from './app.component';

// Load runtime config before bootstrapping so GATEWAY_URL is available
// In local dev: config.json has gatewayUrl="" → app uses relative /api (proxy)
// In production: config.json is replaced by the build script with the real URL
fetch('/config.json')
  .then(r => r.ok ? r.json() : {})
  .catch(() => ({}))
  .then((cfg: { gatewayUrl?: string }) => {
    // Expose globally — Angular HttpClient calls use this as base URL prefix
    (window as unknown as Record<string, unknown>)['__GATEWAY_URL__'] =
      (cfg.gatewayUrl ?? '').replace(/\/$/, '');
    return bootstrapApplication(AppComponent, { providers: [provideHttpClient()] });
  })
  .catch(console.error);
