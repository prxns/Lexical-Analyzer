#include <stdio.h>

/* A small program for the Compiler Design demonstration. */
int main(void) {
    int values[3] = {10, 075, 0x2A};
    unsigned int limit = 25U;
    double scale = .5, epsilon = 2e-3;
    char grade = 'A', newline = '\n';
    const char *message = "Total:\t";
    int total = 0;
    // Accumulate values and exercise longest-match operators.
    for (int i = 0; i < 3; i++) {
        total += values[i];
    }
    if (total >= 10 && total != 0) {
        printf("%s%.2f %c%c", message, total * scale + epsilon, grade, newline);
    }
    return total > (int)limit ? 0 : 1;
}
