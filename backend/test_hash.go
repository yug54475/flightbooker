package main

import (
	"fmt"
	"golang.org/x/crypto/bcrypt"
)

func main() {
	hash, err := bcrypt.GenerateFromPassword([]byte("demo1234"), 12)
	if err != nil {
		fmt.Println("Error:", err)
	} else {
		fmt.Println("Hash:", string(hash))
	}
}
