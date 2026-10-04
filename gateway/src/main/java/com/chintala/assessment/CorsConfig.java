package com.chintala.assessment;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * CORS configuration for the gateway.
 *
 * ALLOWED_ORIGINS is a comma-separated list of trusted front-end origins.
 * Example: https://clinready-ui.onrender.com,https://clinready.vercel.app
 *
 * Defaults to * (all origins) so local development works without any config.
 * Set ALLOWED_ORIGINS in the Render environment to lock down production.
 */
@Configuration
public class CorsConfig implements WebMvcConfigurer {

    @Value("${assessment.allowed-origins:*}")
    private String allowedOrigins;

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        String[] origins = allowedOrigins.equals("*")
            ? new String[]{"*"}
            : allowedOrigins.split(",");

        registry.addMapping("/api/**")
            .allowedOrigins(origins)
            .allowedMethods("GET", "POST", "OPTIONS")
            .allowedHeaders("Authorization", "Content-Type", "Idempotency-Key")
            .exposedHeaders("Content-Type")
            .allowCredentials(!allowedOrigins.equals("*"))
            .maxAge(3600);
    }
}
