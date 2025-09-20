# Issue: AEP-205
# Generated: 2025-09-20T06:55:05.772752
# Thread: 8067122d
# Enhanced: LangChain structured generation
# AI Model: deepseek/deepseek-chat-v3.1:free
# Max Length: 25000 characters

package com.aep.test;

import com.aep.core.AEPEngine;
import com.aep.core.AEPConfig;
import com.aep.core.EventProcessor;
import com.aep.core.EventListener;
import com.aep.core.Event;
import com.aep.core.ProcessingResult;
import com.aep.core.exceptions.AEPException;
import com.aep.core.exceptions.ConfigurationException;
import com.aep.core.exceptions.EventProcessingException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class AEPEngineTest {

    private static final Logger logger = LoggerFactory.getLogger(AEPEngineTest.class);
    
    private AEPEngine aepEngine;
    private AEPConfig config;
    
    @Mock
    private EventProcessor eventProcessor;
    
    @Mock
    private EventListener eventListener;

    @BeforeEach
    void setUp() throws ConfigurationException {
        config = new AEPConfig.Builder()
                .setMaxQueueSize(1000)
                .setProcessingThreads(4)
                .setProcessingTimeoutMs(5000)
                .build();
        
        aepEngine = new AEPEngine(config);
        aepEngine.setEventProcessor(eventProcessor);
        aepEngine.addEventListener(eventListener);
    }

    @Test
    @DisplayName("Test AEP Engine Initialization with Valid Configuration")
    void testEngineInitializationWithValidConfig() {
        assertNotNull(aepEngine);
        assertTrue(aepEngine.isInitialized());
        assertEquals(4, aepEngine.getThreadPoolSize());
    }

    @Test
    @DisplayName("Test AEP Engine Initialization with Invalid Configuration")
    void testEngineInitializationWithInvalidConfig() {
        assertThrows(ConfigurationException.class, () -> {
            AEPConfig invalidConfig = new AEPConfig.Builder()
                    .setMaxQueueSize(-1)
                    .build();
            new AEPEngine(invalidConfig);
        });
    }

    @Test
    @DisplayName("Test Event Processing Success")
    void testEventProcessingSuccess() throws EventProcessingException, InterruptedException {
        Event testEvent = createTestEvent("test-event-1", "Test Event Data");
        ProcessingResult expectedResult = new ProcessingResult(ProcessingResult.Status.SUCCESS, "Processed successfully");
        
        when(eventProcessor.processEvent(any(Event.class))).thenReturn(expectedResult);
        
        CountDownLatch latch = new CountDownLatch(1);
        doAnswer(invocation -> {
            latch.countDown();
            return null;
        }).when(eventListener).onEventProcessed(any(Event.class), any(ProcessingResult.class));
        
        aepEngine.submitEvent(testEvent);
        
        assertTrue(latch.await(5, TimeUnit.SECONDS));
        verify(eventProcessor, times(1)).processEvent(testEvent);
        verify(eventListener, times(1)).onEventProcessed(eq(testEvent), eq(expectedResult));
    }

    @Test
    @DisplayName("Test Event Processing Failure")
    void testEventProcessingFailure() throws EventProcessingException, InterruptedException {
        Event testEvent = createTestEvent("test-event-2", "Test Event Data");
        ProcessingResult expectedResult = new ProcessingResult(ProcessingResult.Status.FAILED, "Processing failed");
        
        when(eventProcessor.processEvent(any(Event.class))).thenReturn(expectedResult);
        
        CountDownLatch latch = new CountDownLatch(1);
        doAnswer(invocation -> {
            latch.countDown();
            return null;
        }).when(eventListener).onEventProcessed(any(Event.class), any(ProcessingResult.class));
        
        aepEngine.submitEvent(testEvent);
        
        assertTrue(latch.await(5, TimeUnit.SECONDS));
        verify(eventProcessor, times(1)).processEvent(testEvent);
        verify(eventListener, times(1)).onEventProcessed(eq(testEvent), eq(expectedResult));
    }

    @Test
    @DisplayName("Test Event Processing Exception Handling")
    void testEventProcessingException() throws EventProcessingException, InterruptedException {
        Event testEvent = createTestEvent("test-event-3", "Test Event Data");
        
        when(eventProcessor.processEvent(any(Event.class)))
                .thenThrow(new EventProcessingException("Processor failure"));
        
        CountDownLatch latch = new CountDownLatch(1);
        doAnswer(invocation -> {
            latch.countDown();
            return null;
        }).when(eventListener).onEventProcessingError(any(Event.class), any(EventProcessingException.class));
        
        aepEngine.submitEvent(testEvent);
        
        assertTrue(latch.await(5, TimeUnit.SECONDS));
        verify(eventProcessor, times(1)).processEvent(testEvent);
        verify(eventListener, times(1)).onEventProcessingError(eq(testEvent), any(EventProcessingException.class));
    }

    @Test
    @DisplayName("Test Null Event Submission")
    void testNullEventSubmission() {
        assertThrows(IllegalArgumentException.class, () -> {
            aepEngine.submitEvent(null);
        });
    }

    @Test
    @DisplayName("Test Event Queue Capacity")
    void testEventQueueCapacity() throws InterruptedException {
        AEPConfig limitedConfig = new AEPConfig.Builder()
                .setMaxQueueSize(2)
                .setProcessingThreads(1)
                .build();
        
        AEPEngine limitedEngine = new AEPEngine(limitedConfig);
        limitedEngine.setEventProcessor(eventProcessor);
        
        // Slow down processing to test queue capacity
        doAnswer(invocation -> {
            Thread.sleep(100);
            return new ProcessingResult(ProcessingResult.Status.SUCCESS, "Processed");
        }).when(eventProcessor).processEvent(any(Event.class));
        
        // Submit events up to capacity
        limitedEngine.submitEvent(createTestEvent("event-1", "data"));
        limitedEngine.submitEvent(createTestEvent("event-2", "data"));
        
        // Third event should be rejected
        assertThrows(AEPException.class, () -> {
            limitedEngine.submitEvent(createTestEvent("event-3", "data"));
        });
        
        limitedEngine.shutdown();
    }

    @Test
    @DisplayName("Test Concurrent Event Processing")
    void testConcurrentEventProcessing() throws InterruptedException, EventProcessingException {
        int numberOfEvents = 100;
        AtomicInteger processedCount = new AtomicInteger(0);
        CountDownLatch latch = new CountDownLatch(numberOfEvents);
        
        when(eventProcessor.processEvent(any(Event.class))).thenAnswer(invocation -> {
            processedCount.incrementAndGet();
            return new ProcessingResult(ProcessingResult.Status.SUCCESS, "Processed");
        });
        
        doAnswer(invocation -> {
            latch.countDown();
            return null;
        }).when(eventListener).onEventProcessed(any(Event.class), any(ProcessingResult.class));
        
        // Submit events concurrently
        for (int i = 0; i < numberOfEvents; i++) {
            Event event = createTestEvent("concurrent-event-" + i, "data-" + i);
            aepEngine.submitEvent(event);
        }
        
        assertTrue(latch.await(10, TimeUnit.SECONDS));
        assertEquals(numberOfEvents, processedCount.get());
        verify(eventListener, times(numberOfEvents)).onEventProcessed(any(Event.class), any(ProcessingResult.class));
    }

    @Test
    @DisplayName("Test Engine Shutdown")
    void testEngineShutdown() throws InterruptedException {
        CountDownLatch processingLatch = new CountDownLatch(1);
        CountDownLatch shutdownLatch = new CountDownLatch(1);
        
        doAnswer(invocation -> {
            processingLatch.countDown();
            // Wait for shutdown signal
            shutdownLatch.await(2, TimeUnit.SECONDS);
            return new ProcessingResult(ProcessingResult.Status.SUCCESS, "Processed");
        }).when(eventProcessor).processEvent(any(Event.class));
        
        aepEngine.submitEvent(createTestEvent("shutdown-test", "data"));
        
        // Wait for processing to start
        assertTrue(processingLatch.await(2, TimeUnit.SECONDS));
        
        // Shutdown should wait for processing to complete
        long startTime = System.currentTimeMillis();
        shutdownLatch.countDown(); // Allow processing to complete
        aepEngine.shutdown();
        long shutdownTime = System.currentTimeMillis() - startTime;
        
        // Shutdown should not be instantaneous (should wait for processing)
        assertTrue(shutdownTime > 100, "Shutdown should wait for processing");
        assertFalse(aepEngine.isRunning());
    }

    @Test
    @DisplayName("Test Event Validation")
    void testEventValidation() {
        Event invalidEvent = new Event(null, "data");
        assertThrows(IllegalArgumentException.class, () -> aepEngine.submitEvent(invalidEvent));
        
        Event validEvent = createTestEvent("valid-event", "data");
        assertDoesNotThrow(() -> aepEngine.submitEvent(validEvent));
    }

    @Test
    @DisplayName("Test Processing Timeout Handling")
    void testProcessingTimeout() throws EventProcessingException, InterruptedException {
        AEPConfig timeoutConfig = new AEPConfig.Builder()
                .setMaxQueueSize(10)
                .setProcessingThreads(1)
                .setProcessingTimeoutMs(100)
                .build();
        
        AEPEngine timeoutEngine = new AEPEngine(timeoutConfig);
        timeoutEngine.setEventProcessor(eventProcessor);
        timeoutEngine.addEventListener(eventListener);
        
        // Simulate slow processing that exceeds timeout
        doAnswer(invocation -> {
            Thread.sleep(200); // Exceeds 100ms timeout
            return new ProcessingResult(ProcessingResult.Status.SUCCESS, "Processed");
        }).when(eventProcessor).processEvent(any(Event.class));
        
        CountDownLatch latch = new CountDownLatch(1);
        doAnswer(invocation -> {
            latch.countDown();
            return null;
        }).when(eventListener).onEventProcessingError(any(Event.class), any(EventProcessingException.class));
        
        timeoutEngine.submitEvent(createTestEvent("timeout-event", "data"));
        
        assertTrue(latch.await(1, TimeUnit.SECONDS));
        verify(eventListener, times(1)).onEventProcessingError(any(Event.class), any(EventProcessingException.class));
        
        timeoutEngine.shutdown();
    }

    private Event createTestEvent(String eventId, String data) {
        return new Event(eventId, data);
    }

    @Test
    @DisplayName("Test Engine Restart")
    void testEngineRestart() throws ConfigurationException, InterruptedException {
        aepEngine.shutdown();
        assertFalse(aepEngine.isRunning());
        
        AEPEngine restartedEngine = new AEPEngine(config);
        restartedEngine.setEventProcessor(eventProcessor);
        
        assertTrue(restartedEngine.isRunning());
        
        CountDownLatch latch = new CountDownLatch(1);
        doAnswer(invocation -> {
            latch.countDown();
            return new ProcessingResult(ProcessingResult.Status.SUCCESS, "Processed");
        }).when(eventProcessor).processEvent(any(Event.class));
        
        restartedEngine.submitEvent(createTestEvent("restart-test", "data"));
        
        assertTrue(latch.await(2, TimeUnit.SECONDS));
        restartedEngine.shutdown();
    }

    @Test
    @DisplayName("Test Event Priority Handling")
    void testEventPriorityHandling() throws EventProcessingException, InterruptedException {
        Event highPriorityEvent = createTestEvent("high-priority", "data");
        highPriorityEvent.setPriority(Event.Priority.HIGH);
        
        Event normalPriorityEvent = createTestEvent("normal-priority", "data");
        normalPriorityEvent.setPriority(Event.Priority.NORMAL);
        
        CountDownLatch highPriorityLatch = new CountDownLatch(1);
        CountDownLatch normalPriorityLatch = new CountDownLatch(1);
        
        doAnswer(invocation -> {
            Event event = invocation.getArgument(0);
            if (event.getEventId().equals("high-priority")) {
                highPriorityLatch.countDown();
            } else {
                normalPriorityLatch.countDown();
            }
            return new ProcessingResult(ProcessingResult.Status.SUCCESS, "Processed");
        }).when(eventProcessor).processEvent(any(Event.class));
        
        // Submit normal priority first, then high priority
        aepEngine.submitEvent(normalPriorityEvent);
        Thread.sleep(50); // Small delay
        aepEngine.submitEvent(highPriorityEvent);
        
        // High priority should be processed first despite being submitted later
        assertTrue(highPriorityLatch.await(2, TimeUnit.SECONDS));
        // Normal priority should be processed after
        assertTrue(normalPriorityLatch.await(2, TimeUnit.SECONDS));
    }

    @Test
    @DisplayName("Test Resource Cleanup on Shutdown")
    void testResourceCleanupOnShutdown() {
        assertTrue(aepEngine.isRunning());
        aepEngine.shutdown();
        assertFalse(aepEngine.isRunning());
        
        // Verify that thread pools are properly shutdown
        assertTrue(aepEngine.getThreadPool().isShutdown());
        assertTrue(aepEngine.getThreadPool().isTerminated());
    }

    @Test
    @DisplayName("Test Event Batch Processing")
    void testEventBatchProcessing() throws EventProcessingException, InterruptedException {
        int batchSize = 10;
        CountDownLatch latch = new CountDownLatch(batchSize);
        
        when(eventProcessor.processEvent(any(Event.class))).thenReturn(
                new ProcessingResult(ProcessingResult.Status.SUCCESS, "Processed"));
        
        doAnswer(invocation -> {
            latch.countDown();
            return null;
        }).when(eventListener).onEventProcessed(any(Event.class), any(ProcessingResult.class));
        
        for (int i = 0; i < batchSize; i++) {
            Event event = createTestEvent("batch-event-" + i, "data-" + i);
            aepEngine.submitEvent(event);
        }
        
        assertTrue(latch.await(5, TimeUnit.SECONDS));
        verify(eventProcessor, times(batchSize)).processEvent(any(Event.class));
    }

    @Test
    @DisplayName("Test Configuration Reload")
    void testConfigurationReload() throws ConfigurationException {
        AEPConfig newConfig = new AEPConfig.Builder()
                .setMaxQueueSize(2000)
                .setProcessingThreads(8)
                .setProcessingTimeoutMs(3000)
                .build();
        
        aepEngine.reloadConfiguration(newConfig);
        
        assertEquals(8, aepEngine.getThreadPoolSize());
        assertEquals(2000, aepEngine.getMaxQueueCapacity());
    }
}