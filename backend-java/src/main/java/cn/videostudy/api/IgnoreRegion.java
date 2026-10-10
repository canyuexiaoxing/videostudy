package cn.videostudy.api;

import com.fasterxml.jackson.databind.ObjectMapper;

/** Rectangle in displayed video coordinates, normalized to [0, 1]. */
public record IgnoreRegion(double x, double y, double width, double height) {
    public IgnoreRegion {
        if (!Double.isFinite(x) || !Double.isFinite(y) || !Double.isFinite(width) || !Double.isFinite(height)
            || x < 0 || y < 0 || x >= 1 || y >= 1 || width <= 0 || height <= 0 || x + width > 1 + 1e-9
            || y + height > 1 + 1e-9 || width * height > .95)
            throw new IllegalArgumentException("invalid_ignored_region");
        width = Math.min(width, 1 - x); height = Math.min(height, 1 - y);
    }

    public static IgnoreRegion parse(String value) {
        if (value == null || value.isBlank()) return null;
        try {
            var parser = new ObjectMapper();
            try (var tokens = parser.createParser(value)) {
                com.fasterxml.jackson.databind.JsonNode node = parser.readTree(tokens);
                if (tokens.nextToken() != null || node == null || !node.isObject() || node.size() != 4)
                    throw new IllegalArgumentException("invalid_ignored_region");
                for (var name : java.util.List.of("x", "y", "width", "height"))
                    if (!node.has(name) || !node.get(name).isNumber())
                        throw new IllegalArgumentException("invalid_ignored_region");
                return new IgnoreRegion(node.get("x").doubleValue(), node.get("y").doubleValue(),
                    node.get("width").doubleValue(), node.get("height").doubleValue());
            }
        } catch (Exception error) { throw new IllegalArgumentException("invalid_ignored_region", error); }
    }
}
