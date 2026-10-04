FROM gradle:8.13-jdk17 AS build
WORKDIR /workspace
COPY settings.gradle build.gradle ./
COPY src ./src
RUN gradle --no-daemon test bootJar
FROM eclipse-temurin:17-jre
WORKDIR /app
RUN useradd --system --uid 10001 appuser
COPY --from=build /workspace/build/libs/assessment-gateway-0.1.0.jar app.jar
USER appuser
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
