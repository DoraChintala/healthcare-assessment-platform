package com.chintala.assessment;

import java.net.http.HttpClient;
import java.time.Duration;
import java.util.UUID;
import com.fasterxml.jackson.databind.JsonNode;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.client.ResourceAccessException;

@RestController
@RequestMapping("/api")
public class AssessmentController {
    private final RestClient client;
    private final String serviceToken;
    public AssessmentController(@Value("${assessment.ai-url}") String url,
                                @Value("${assessment.service-token}") String serviceToken) {
        this.serviceToken = serviceToken;
        var factory = new JdkClientHttpRequestFactory(HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build());
        factory.setReadTimeout(Duration.ofSeconds(15));
        client = RestClient.builder().baseUrl(url).requestFactory(factory).build();
    }
    private String id(String value) { return UUID.fromString(value).toString(); }
    private ResponseEntity<String> forward(HttpMethod method, String path, JsonNode body, String key, HttpServletRequest request) {
        try {
            var spec = client.method(method).uri(path)
                .header("X-Service-Token", serviceToken)
                .header("X-Tenant-ID", String.valueOf(request.getAttribute("tenant")))
                .header("X-Actor-ID", String.valueOf(request.getAttribute("actor")))
                .header("X-Role", String.valueOf(request.getAttribute("role")))
                .contentType(MediaType.APPLICATION_JSON);
            if (key != null) spec.header("Idempotency-Key", key);
            if (body != null) spec.body(body);
            var result = spec.retrieve().toEntity(String.class);
            return ResponseEntity.status(result.getStatusCode()).contentType(MediaType.APPLICATION_JSON).body(result.getBody());
        } catch (RestClientResponseException e) {
            return ResponseEntity.status(e.getStatusCode()).contentType(MediaType.APPLICATION_JSON).body(e.getResponseBodyAsString());
        } catch (ResourceAccessException e) {
            return ResponseEntity.status(503).body("{\"detail\":\"AI service unavailable\"}");
        }
    }
    @GetMapping("/jobs") public ResponseEntity<String> jobs(HttpServletRequest req) { return forward(HttpMethod.GET,"/jobs",null,null,req); }
    @GetMapping("/samples") public ResponseEntity<String> samples(HttpServletRequest req) { return forward(HttpMethod.GET,"/samples",null,null,req); }
    @GetMapping("/assessments") public ResponseEntity<String> list(HttpServletRequest req) { return forward(HttpMethod.GET,"/assessments",null,null,req); }
    @PostMapping("/assessments") public ResponseEntity<String> create(@RequestBody JsonNode body,@RequestHeader("Idempotency-Key") String key,HttpServletRequest req) {
        return forward(HttpMethod.POST,"/assessments",body,key,req);
    }
    @GetMapping("/assessments/{id}") public ResponseEntity<String> get(@PathVariable String id,HttpServletRequest req) { return forward(HttpMethod.GET,"/assessments/"+id(id),null,null,req); }
    @GetMapping("/assessments/{id}/audit") public ResponseEntity<String> audit(@PathVariable String id,HttpServletRequest req) { return forward(HttpMethod.GET,"/assessments/"+id(id)+"/audit",null,null,req); }
    @PostMapping("/assessments/{id}/review") public ResponseEntity<String> review(@PathVariable String id,@RequestBody JsonNode body,HttpServletRequest req) {
        return forward(HttpMethod.POST,"/assessments/"+id(id)+"/review",body,null,req);
    }
    @ExceptionHandler(IllegalArgumentException.class) public ResponseEntity<String> badId() {
        return ResponseEntity.badRequest().body("{\"detail\":\"Invalid assessment ID\"}");
    }
}
