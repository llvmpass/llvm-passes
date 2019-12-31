#include <stdlib.h>
#include <stdio.h>
#include <time.h>

#if defined(NUMBER_OF_ITERATIONS) && NUMBER_OF_ITERATIONS == 0
#undef NUMBER_OF_ITERATIONS
#endif

#ifndef NUMBER_OF_ITERATIONS
#define NUMBER_OF_ITERATIONS    1
#define NO_CACHING
#endif

#define EXPERIMENT_FAIL -1

/*
 Usage to wrap a file and measure its time :
 clang -c [FILE TO COMPILE] -o file.o
 objcopy --redefine-sym main=old_main file.o
 clang -c wrapper.c -o wrap.o -D NUMBER_OF_ITERATIONS=50
 clang file.o wrap.o -o wrapped_exec
 ./wrapped_exec
 cat wrappertime.txt

 -> Runs the main function 50 times, writes the result in wrappertime.txt, display its content
*/

// TODO : Be compatible with args
// TODO : what if main() in the tested program ends with exit(0) instead of return 0

// Function to test
int old_main();


// Write in a file the elapsed time
int note_time(long elapsed_time, long total_elapsed_time) {
    // TODO : we could also transmit the time with a pipe or a socket

    FILE * file = fopen("wrappertime.txt", "w");
    if (file == NULL) {
        perror("fopen");
        return -1;
    }

    if (elapsed_time != EXPERIMENT_FAIL) {
        fprintf(file, "Number of iterations : %d\n", NUMBER_OF_ITERATIONS);
        fprintf(file, "Elapsed time (ns) : %ld\n", elapsed_time);
        fprintf(file, "Total elapsed time (ns) : %ld\n", total_elapsed_time);
    } else {
        fprintf(file, "Failure\n");
    }

    int r = fclose(file);
    if (r != 0) {
        perror("fclose");
    }
    return r;
}


// Calculate the difference between the two given timespec.
long calculate_time_diff(struct timespec begin, struct timespec end) {
    long elapsed_time = 0;
    elapsed_time = end.tv_nsec - begin.tv_nsec;

    double elapsed_time_sec = difftime(end.tv_sec, begin.tv_sec);
    elapsed_time += ((int) elapsed_time_sec) * 1e+9;

    return elapsed_time;
}


// Actual main function. Not called main to be able to change symbol during linking
int main() {
#ifndef NO_CACHING
    // Caching
    if (NUMBER_OF_ITERATIONS != 1)
        old_main();
#endif

    struct timespec begin;
    struct timespec end;

    struct timespec absolute_begin;
    struct timespec absolute_end;

    long min_measured_time = -1;

	clock_gettime(CLOCK_MONOTONIC, &absolute_begin);

    // Main loop
	for (long i = 0 ; i < NUMBER_OF_ITERATIONS ; i++) {
	    // Measure an execution
	    clock_gettime(CLOCK_MONOTONIC, &begin);

        if (old_main()) {
            note_time(EXPERIMENT_FAIL, EXPERIMENT_FAIL);
            return -1;
        }

        clock_gettime(CLOCK_MONOTONIC, &end);

        // Note the time
        long elapsed_time = calculate_time_diff(begin, end);

        if (min_measured_time == -1 || min_measured_time > elapsed_time) {
            min_measured_time = elapsed_time;
        }
    }

	clock_gettime(CLOCK_MONOTONIC, &absolute_end);


    // Send the time to python script
    note_time(min_measured_time, calculate_time_diff(absolute_begin, absolute_end));
    
	return 0;
}
