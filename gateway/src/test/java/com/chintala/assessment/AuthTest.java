package com.chintala.assessment;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.*;
import static org.junit.jupiter.api.Assertions.*;

class AuthTest {
    private final DemoAuthFilter filter = new DemoAuthFilter("reviewer-token","viewer-token");
    @Test void unauthenticatedRequestIsRejected() throws Exception {
        var req = new MockHttpServletRequest("GET","/api/assessments");
        var res = new MockHttpServletResponse();
        filter.doFilter(req,res,new MockFilterChain());
        assertEquals(401,res.getStatus());
    }
    @Test void viewerCannotReview() throws Exception {
        var req = new MockHttpServletRequest("POST","/api/assessments/abc/review");
        req.addHeader("Authorization","Bearer viewer-token");
        var res = new MockHttpServletResponse();
        filter.doFilter(req,res,new MockFilterChain());
        assertEquals(403,res.getStatus());
    }
    @Test void callerCannotOverrideTenant() throws Exception {
        var req = new MockHttpServletRequest("GET","/api/assessments");
        req.addHeader("Authorization","Bearer reviewer-token");
        req.addHeader("X-Tenant-ID","other-hospital");
        filter.doFilter(req,new MockHttpServletResponse(),new MockFilterChain());
        assertEquals("demo-hospital",req.getAttribute("tenant"));
    }
}
