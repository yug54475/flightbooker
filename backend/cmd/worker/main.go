package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/joho/godotenv"
	"github.com/yug54475/flightbooker/internal/db"
	"github.com/yug54475/flightbooker/internal/queue"
	"github.com/yug54475/flightbooker/internal/worker"
)

func main() {
	// Load .env file
	if err := godotenv.Load(); err != nil {
		log.Println("No .env file found, using environment variables")
	}

	// Connect to database
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := db.Connect(ctx); err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()
	log.Println("Worker connected to Postgres")

	// Initialize SQS
	if err := queue.Init(ctx); err != nil {
		log.Fatalf("Failed to initialize SQS: %v", err)
	}
	log.Println("Worker connected to SQS")

	// Graceful shutdown (§12.5)
	shutdownCtx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	var wg sync.WaitGroup

	// Start approval timeout ticker (§7.1)
	wg.Add(1)
	go func() {
		defer wg.Done()
		worker.RunApprovalTimeoutTicker(shutdownCtx)
	}()

	// Start SQS consumer
	wg.Add(1)
	go func() {
		defer wg.Done()
		log.Println("SQS consumer starting...")
		queue.Consume(shutdownCtx, worker.HandleMessage)
	}()

	log.Println("Worker is running. Press Ctrl+C to stop.")

	// Wait for shutdown signal
	<-shutdownCtx.Done()
	log.Println("Worker shutdown signal received, waiting for in-flight work...")

	// Give in-flight work time to complete
	wg.Wait()
	fmt.Println("Worker stopped gracefully")
}
