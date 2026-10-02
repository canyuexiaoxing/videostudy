package cn.videostudy.api;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class TranscriptionDeletionControllerTest {
    @TempDir Path temporaryDirectory;

    @Test
    void completedJobDeletionRemovesOnlyItsUploadFramesAndStoredResult() throws Exception {
        var id = UUID.randomUUID().toString();
        var otherId = UUID.randomUUID().toString();
        var uploads = Files.createDirectory(temporaryDirectory.resolve("uploads"));
        var frames = Files.createDirectory(temporaryDirectory.resolve("frames"));
        var upload = Files.write(uploads.resolve(id), new byte[] {1});
        var frameDirectory = Files.createDirectories(frames.resolve(id).resolve("nested"));
        Files.write(frameDirectory.resolve("1000.jpg"), new byte[] {2});
        var otherFrame = Files.write(Files.createDirectory(frames.resolve(otherId)).resolve("2000.jpg"), new byte[] {3});
        var store = mock(TranscriptionJobStore.class);
        when(store.find(id)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(id, "completed", null, null)));
        var controller = new TranscriptionDeletionController(uploads.toString(), frames.toString(), store);

        MockMvcBuilders.standaloneSetup(controller).build().perform(delete("/api/transcriptions/{id}", id))
            .andExpect(status().isNoContent());

        assertFalse(Files.exists(upload));
        assertFalse(Files.exists(frames.resolve(id)));
        assertTrue(Files.exists(otherFrame));
        verify(store).delete(id);
    }

    @Test
    void activeJobCannotBeDeletedWhileAnalyzerMayStillWriteResults() throws Exception {
        var id = UUID.randomUUID().toString();
        var uploads = Files.createDirectory(temporaryDirectory.resolve("uploads"));
        var frames = Files.createDirectory(temporaryDirectory.resolve("frames"));
        var upload = Files.write(uploads.resolve(id), new byte[] {1});
        var store = mock(TranscriptionJobStore.class);
        when(store.find(id)).thenReturn(Optional.of(new TranscriptionController.TranscriptionJob(id, "processing", null, null)));
        var controller = new TranscriptionDeletionController(uploads.toString(), frames.toString(), store);

        MockMvcBuilders.standaloneSetup(controller).build().perform(delete("/api/transcriptions/{id}", id))
            .andExpect(status().isConflict())
            .andExpect(jsonPath("$.error").value("analysis_in_progress"));

        assertTrue(Files.exists(upload));
        verify(store, never()).delete(id);
    }

    @Test
    void rejectsInvalidOrUnknownIdsWithoutTouchingFiles() throws Exception {
        var uploads = Files.createDirectory(temporaryDirectory.resolve("uploads"));
        var frames = Files.createDirectory(temporaryDirectory.resolve("frames"));
        var sentinel = Files.write(temporaryDirectory.resolve("sentinel"), new byte[] {1});
        var store = mock(TranscriptionJobStore.class);
        var controller = new TranscriptionDeletionController(uploads.toString(), frames.toString(), store);
        var mvc = MockMvcBuilders.standaloneSetup(controller).build();

        mvc.perform(delete("/api/transcriptions/{id}", "not-a-uuid"))
            .andExpect(status().isBadRequest());
        mvc.perform(delete("/api/transcriptions/{id}", UUID.randomUUID().toString()))
            .andExpect(status().isNotFound());
        assertTrue(Files.exists(sentinel));
        verify(store, never()).delete(org.mockito.ArgumentMatchers.anyString());
    }
}
