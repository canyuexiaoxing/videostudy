package cn.videostudy.api;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.mock.web.MockMultipartFile;
import java.nio.file.Path;
import static org.junit.jupiter.api.Assertions.*;

class CompatibilityControllerTest {
    @TempDir Path directory;
    private CompatibilityController controller() {
        return new CompatibilityController(directory.toString(), "http://127.0.0.1:1");
    }
    @Test void invalidIdentifiersCannotReadOrDeleteFiles() {
        var controller = controller();
        assertEquals(400, controller.status("../secret").getStatusCode().value());
        assertEquals(400, controller.video("../secret").getStatusCode().value());
        assertEquals(400, controller.delete("../secret").getStatusCode().value());
    }
    @Test void emptyUploadIsRejectedWithoutCallingAgent() throws Exception {
        assertEquals(400, controller().upload(new MockMultipartFile("file", new byte[0])).getStatusCode().value());
    }
    @Test void failedAgentConnectionDoesNotRetainUploadedVideo() {
        assertThrows(RuntimeException.class, () -> controller().upload(new MockMultipartFile("file", new byte[]{1,2,3})));
        assertFalse(java.nio.file.Files.exists(directory.resolve("compatibility")) && hasJobs());
    }
    private boolean hasJobs() {
        try (var paths = java.nio.file.Files.list(directory.resolve("compatibility"))) { return paths.findAny().isPresent(); }
        catch (java.io.IOException error) { throw new RuntimeException(error); }
    }
}
