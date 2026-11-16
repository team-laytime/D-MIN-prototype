# syntax=docker/dockerfile:1
# D-MIN-server와 같은 2단계 빌드. Gradle 캐시를 BuildKit 캐시로 남겨 다시 빌드할 때 의존성을 받지 않는다.
FROM eclipse-temurin:25-jdk AS build
WORKDIR /workspace
COPY gradlew settings.gradle build.gradle ./
COPY gradle gradle
RUN --mount=type=cache,target=/root/.gradle ./gradlew --no-daemon -q dependencies > /dev/null
COPY src src
# 단위 테스트(계산 엔진 정답 대조 포함)를 통과해야 이미지가 만들어진다.
RUN --mount=type=cache,target=/root/.gradle ./gradlew --no-daemon test bootJar

FROM eclipse-temurin:25-jre
WORKDIR /app
RUN useradd --system --uid 10001 app
COPY --from=build /workspace/build/libs/*.jar app.jar
USER 10001
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
