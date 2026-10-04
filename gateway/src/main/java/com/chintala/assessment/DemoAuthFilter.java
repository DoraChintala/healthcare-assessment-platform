package com.chintala.assessment;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/** Local demo authentication. Replace with validated OIDC JWT claims before public deployment. */
@Component
public class DemoAuthFilter extends OncePerRequestFilter {
    private final String reviewer;
    private final String viewer;
    public DemoAuthFilter(@Value("${assessment.reviewer-token}") String reviewer,
                          @Value("${assessment.viewer-token}") String viewer) {
        if (reviewer.isBlank() || viewer.isBlank() || reviewer.equals(viewer)) {
            throw new IllegalArgumentException("Distinct nonempty demo credentials required");
        }
        this.reviewer = reviewer; this.viewer = viewer;
    }
    private boolean matches(String a, String b) {
        return MessageDigest.isEqual(a.getBytes(StandardCharsets.UTF_8), b.getBytes(StandardCharsets.UTF_8));
    }
    @Override protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
            throws ServletException, IOException {
        // Let CORS preflight requests through without auth. The browser sends an
        // OPTIONS request with no Authorization header before the real call;
        // blocking it here would break all cross-origin requests.
        if ("OPTIONS".equalsIgnoreCase(req.getMethod())) { chain.doFilter(req,res); return; }
        if (!req.getRequestURI().startsWith("/api/")) { chain.doFilter(req,res); return; }
        String auth = req.getHeader("Authorization");
        String token = auth != null && auth.startsWith("Bearer ") ? auth.substring(7) : "";
        String role = matches(token, reviewer) ? "reviewer" : (matches(token, viewer) ? "viewer" : null);
        if (role == null) { res.sendError(401,"Demo authentication required"); return; }
        req.setAttribute("tenant", "demo-hospital");
        req.setAttribute("actor", "demo-" + role);
        req.setAttribute("role", role);
        if (req.getRequestURI().endsWith("/review") && !role.equals("reviewer")) {
            res.sendError(403,"Reviewer role required"); return;
        }
        chain.doFilter(req,res);
    }
}
