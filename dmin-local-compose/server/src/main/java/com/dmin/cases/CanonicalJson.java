package com.dmin.cases;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HexFormat;
import java.util.List;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.databind.node.ArrayNode;
import tools.jackson.databind.node.ObjectNode;

/** 키를 정렬한 JSON과 그 지문. 같은 데이터가 두 번 들어오면 같은 지문이 나온다(NFR-02 같은 입력 → 같은 답). */
final class CanonicalJson {

    private CanonicalJson() {}

    static JsonNode sorted(ObjectMapper json, JsonNode node) {
        if (node.isObject()) {
            ObjectNode out = json.createObjectNode();
            List<String> names = new ArrayList<>(node.propertyNames());
            Collections.sort(names);
            for (String n : names) {
                out.set(n, sorted(json, node.get(n)));
            }
            return out;
        }
        if (node.isArray()) {
            ArrayNode out = json.createArrayNode();
            for (JsonNode v : node.values()) {
                out.add(sorted(json, v));
            }
            return out;
        }
        return node;
    }

    static String hash(ObjectMapper json, JsonNode node) {
        try {
            byte[] h = MessageDigest.getInstance("SHA-256")
                    .digest(json.writeValueAsString(sorted(json, node)).getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(h).substring(0, 16);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
