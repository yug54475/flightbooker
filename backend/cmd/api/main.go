package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
	"github.com/joho/godotenv"
	"github.com/yug54475/flightbooker/internal/auth"
	"github.com/yug54475/flightbooker/internal/db"
	"github.com/yug54475/flightbooker/internal/handlers"
	"github.com/yug54475/flightbooker/internal/mockapi"
)

func main() {
	// Load .env file (non-fatal if missing — env vars may already be set)
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
	log.Println("Connected to Postgres")

	// Build router
	r := chi.NewRouter()

	// Global middleware
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)
	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)
	r.Use(middleware.Timeout(30 * time.Second))

	// CORS — restricted to frontend dev origin per §12.4
	allowedOrigin := os.Getenv("CORS_ALLOWED_ORIGIN")
	if allowedOrigin == "" {
		allowedOrigin = "http://localhost:5173"
	}
	r.Use(cors.Handler(cors.Options{
		AllowedOrigins:   []string{allowedOrigin},
		AllowedMethods:   []string{"GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"},
		AllowedHeaders:   []string{"Accept", "Authorization", "Content-Type", "X-CSRF-Token"},
		ExposedHeaders:   []string{"Link"},
		AllowCredentials: true,
		MaxAge:           300,
	}))

	// Health (no auth, no /v1 prefix)
	r.Get("/health", handlers.Health)

	// Public auth routes (no JWT required)
	r.Post("/v1/auth/signup", handlers.Signup)
	r.Post("/v1/auth/login", handlers.Login)

	// Protected routes (JWT required)
	r.Group(func(r chi.Router) {
		r.Use(auth.AuthMiddleware)

		// User
		r.Get("/v1/users/me", handlers.GetMe)
		r.Get("/v1/users/me/policy", handlers.GetPolicy)
		r.Patch("/v1/users/me/policy", handlers.UpdatePolicy)

		// Itineraries
		r.Get("/v1/itineraries/{user_id}", handlers.GetItineraries)

		// Disruptions
		r.Get("/v1/disruptions/{user_id}", handlers.GetDisruptions)
		r.Post("/internal/v1/disruptions/simulate", handlers.SimulateDisruption)

		// Agent proposals
		r.Get("/v1/agent-proposals/{job_id}", handlers.GetAgentProposal)

		// Approvals
		r.Post("/v1/approvals/{approval_id}/respond", handlers.RespondToApproval)

		// Timeline
		r.Get("/v1/timeline/{user_id}", handlers.GetTimeline)

		// Notifications
		r.Get("/v1/notifications/{user_id}", handlers.GetNotifications)

		// Insurance claims
		r.Get("/v1/insurance-claims/{user_id}", handlers.GetInsuranceClaims)
	})

	// Mock APIs (internal — only AI agent calls these, per §1)
	r.Route("/mock/v1/booking", func(r chi.Router) {
		r.Post("/flight-orders", mockapi.BookFlightOrder)
		r.Post("/hotel-orders", mockapi.BookHotelOrder)
		r.Post("/force-next-failure", mockapi.ForceNextFlightFailure)
		r.Post("/force-next-hotel-failure", mockapi.ForceNextHotelFailure)
	})

	// Start server with graceful shutdown (§12.5)
	port := os.Getenv("PORT")
	if port == "" {
		port = "8000"
	}

	srv := &http.Server{
		Addr:         ":" + port,
		Handler:      r,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Graceful shutdown via signal.NotifyContext
	shutdownCtx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	var wg sync.WaitGroup

	wg.Add(1)
	go func() {
		defer wg.Done()
		log.Printf("API server starting on :%s", port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	// Wait for shutdown signal
	<-shutdownCtx.Done()
	log.Println("Shutdown signal received, draining connections...")

	// Give in-flight requests time to complete
	drainCtx, drainCancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer drainCancel()

	if err := srv.Shutdown(drainCtx); err != nil {
		log.Printf("Server shutdown error: %v", err)
	}

	wg.Wait()
	fmt.Println("API server stopped gracefully")
}
