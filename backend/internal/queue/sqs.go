package queue

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/sqs"
	"github.com/aws/aws-sdk-go-v2/service/sqs/types"
)

// Client is the SQS client.
var Client *sqs.Client

// QueueURL is the SQS queue URL.
var QueueURL string
var DLQUrl string

// SQSMessage is the minimal message format per §4.3.
type SQSMessage struct {
	DisruptionEventID string `json:"disruption_event_id"`
	DetectedAt        string `json:"detected_at"`
}

// Init initializes the SQS client and ensures the queue exists.
func Init(ctx context.Context) error {
	endpoint := os.Getenv("AWS_ENDPOINT")
	region := os.Getenv("AWS_REGION")
	if region == "" {
		region = "us-east-1"
	}
	queueName := os.Getenv("SQS_QUEUE_NAME")
	if queueName == "" {
		queueName = "disruption-events"
	}

	// Build custom config for LocalStack
	var cfgOpts []func(*config.LoadOptions) error
	cfgOpts = append(cfgOpts, config.WithRegion(region))
	if endpoint != "" {
		cfgOpts = append(cfgOpts, config.WithCredentialsProvider(
			credentials.NewStaticCredentialsProvider("test", "test", ""),
		))
	}
	cfg, err := config.LoadDefaultConfig(ctx, cfgOpts...)
	if err != nil {
		return fmt.Errorf("failed to load AWS config: %w", err)
	}

	// Create SQS client with custom endpoint for LocalStack
	opts := func(o *sqs.Options) {
		if endpoint != "" {
			o.BaseEndpoint = aws.String(endpoint)
		}
	}
	Client = sqs.NewFromConfig(cfg, opts)

	// Create DLQ
	dlqResult, err := Client.CreateQueue(ctx, &sqs.CreateQueueInput{
		QueueName: aws.String(queueName + "-dlq"),
	})
	if err != nil {
		return fmt.Errorf("failed to create DLQ: %w", err)
	}
	DLQUrl = *dlqResult.QueueUrl

	// Get DLQ ARN
	attrResult, err := Client.GetQueueAttributes(ctx, &sqs.GetQueueAttributesInput{
		QueueUrl:       dlqResult.QueueUrl,
		AttributeNames: []types.QueueAttributeName{types.QueueAttributeNameQueueArn},
	})
	if err != nil {
		return fmt.Errorf("failed to get DLQ attributes: %w", err)
	}
	dlqArn := attrResult.Attributes[string(types.QueueAttributeNameQueueArn)]

	// Create queue if it doesn't exist (idempotent)
	result, err := Client.CreateQueue(ctx, &sqs.CreateQueueInput{
		QueueName: aws.String(queueName),
		Attributes: map[string]string{
			"VisibilityTimeout": "90", // bumped to 90 seconds for retries
			"RedrivePolicy":     fmt.Sprintf(`{"deadLetterTargetArn":"%s","maxReceiveCount":"3"}`, dlqArn),
		},
	})
	if err != nil {
		return fmt.Errorf("failed to create/get SQS queue: %w", err)
	}

	QueueURL = *result.QueueUrl
	log.Printf("SQS queue ready: %s", QueueURL)
	return nil
}

// Publish sends a disruption event message to SQS per §4.3.
func Publish(ctx context.Context, disruptionEventID, detectedAt string) error {
	if Client == nil {
		return fmt.Errorf("SQS client not initialized")
	}

	msg := SQSMessage{
		DisruptionEventID: disruptionEventID,
		DetectedAt:        detectedAt,
	}

	body, err := json.Marshal(msg)
	if err != nil {
		return fmt.Errorf("failed to marshal SQS message: %w", err)
	}

	_, err = Client.SendMessage(ctx, &sqs.SendMessageInput{
		QueueUrl:    aws.String(QueueURL),
		MessageBody: aws.String(string(body)),
	})
	if err != nil {
		return fmt.Errorf("failed to send SQS message: %w", err)
	}

	log.Printf("Published disruption event to SQS: %s", disruptionEventID)
	return nil
}

// Consume long-polls SQS for messages and calls the handler for each one.
// Returns when context is cancelled.
func Consume(ctx context.Context, handler func(ctx context.Context, msg SQSMessage, receiptHandle string) error) {
	if Client == nil {
		log.Println("SQS client not initialized, cannot consume")
		return
	}

	log.Println("SQS consumer started, polling for messages...")

	for {
		select {
		case <-ctx.Done():
			log.Println("SQS consumer stopping (context cancelled)")
			return
		default:
		}

		result, err := Client.ReceiveMessage(ctx, &sqs.ReceiveMessageInput{
			QueueUrl:            aws.String(QueueURL),
			MaxNumberOfMessages: 1,
			WaitTimeSeconds:     10, // Long polling
			MessageAttributeNames: []string{
				string(types.QueueAttributeNameAll),
			},
		})
		if err != nil {
			if ctx.Err() != nil {
				return // Context cancelled, normal shutdown
			}
			log.Printf("Error receiving SQS message: %v", err)
			time.Sleep(2 * time.Second)
			continue
		}

		for _, sqsMsg := range result.Messages {
			var msg SQSMessage
			if err := json.Unmarshal([]byte(*sqsMsg.Body), &msg); err != nil {
				log.Printf("Failed to unmarshal SQS message: %v", err)
				// Don't delete — let it go to the DLQ after 3 failures
				continue
			}

			if err := handler(ctx, msg, *sqsMsg.ReceiptHandle); err != nil {
				log.Printf("Error handling message %s: %v", msg.DisruptionEventID, err)
				// Don't delete — let it become visible again after visibility timeout
				continue
			}

			// Success — delete the message
			deleteMessage(ctx, *sqsMsg.ReceiptHandle)
		}
	}
}

func deleteMessage(ctx context.Context, receiptHandle string) {
	_, err := Client.DeleteMessage(ctx, &sqs.DeleteMessageInput{
		QueueUrl:      aws.String(QueueURL),
		ReceiptHandle: aws.String(receiptHandle),
	})
	if err != nil {
		log.Printf("Failed to delete SQS message: %v", err)
	}
}
