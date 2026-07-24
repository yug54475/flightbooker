package validation

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"

	"github.com/go-playground/validator/v10"
	"github.com/yug54475/flightbooker/internal/models"
)

// Validate is the shared validator instance.
var Validate *validator.Validate

func init() {
	Validate = validator.New()
}

// ValidateStruct validates a struct and returns a formatted error if invalid.
func ValidateStruct(s interface{}) error {
	err := Validate.Struct(s)
	if err == nil {
		return nil
	}

	validationErrors, ok := err.(validator.ValidationErrors)
	if !ok {
		// Deliberate fallback: handles things like InvalidValidationError (e.g. validating a nil pointer).
		// In these edge cases, returning the raw error avoids panics, though it won't have field-level formatting.
		return err
	}

	var messages []string
	for _, e := range validationErrors {
		messages = append(messages, formatFieldError(e))
	}
	return fmt.Errorf("%s", strings.Join(messages, "; "))
}

func formatFieldError(e validator.FieldError) string {
	field := toSnakeCase(e.Field())
	switch e.Tag() {
	case "required":
		return fmt.Sprintf("%s is required", field)
	case "email":
		return fmt.Sprintf("%s must be a valid email address", field)
	case "min":
		return fmt.Sprintf("%s must be at least %s characters", field, e.Param())
	case "max":
		return fmt.Sprintf("%s must be at most %s characters", field, e.Param())
	case "oneof":
		return fmt.Sprintf("%s must be one of: %s", field, e.Param())
	case "uuid":
		return fmt.Sprintf("%s must be a valid UUID", field)
	case "gte":
		return fmt.Sprintf("%s must be >= %s", field, e.Param())
	default:
		return fmt.Sprintf("%s failed validation: %s", field, e.Tag())
	}
}

// toSnakeCase converts PascalCase field names to snake_case for API responses.
// Correctly handles acronyms like UserID -> user_id.
func toSnakeCase(s string) string {
	var result strings.Builder
	runes := []rune(s)
	for i, r := range runes {
		if r >= 'A' && r <= 'Z' {
			// only insert underscore if previous char was lowercase (i.e. genuine word boundary)
			if i > 0 && runes[i-1] >= 'a' && runes[i-1] <= 'z' {
				result.WriteRune('_')
			}
			result.WriteRune(r + 32)
		} else {
			result.WriteRune(r)
		}
	}
	return result.String()
}

// DecodeAndValidate reads JSON body, decodes into dst, and validates.
// Writes a 400 error response on failure and returns false.
func DecodeAndValidate(w http.ResponseWriter, r *http.Request, dst interface{}) bool {
	if err := json.NewDecoder(r.Body).Decode(dst); err != nil {
		WriteError(w, http.StatusBadRequest, "validation_error", "Invalid JSON body: "+err.Error())
		return false
	}

	if err := ValidateStruct(dst); err != nil {
		WriteError(w, http.StatusBadRequest, "validation_error", err.Error())
		return false
	}

	return true
}

// WriteError writes a standardized error response per §3.2.
func WriteError(w http.ResponseWriter, status int, code, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	resp := models.ErrorResponse{
		Error: models.ErrorDetail{
			Code:    code,
			Message: message,
		},
	}
	_ = json.NewEncoder(w).Encode(resp)
}

// WriteJSON writes a successful JSON response.
func WriteJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	enc := json.NewEncoder(w)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(data)
}
