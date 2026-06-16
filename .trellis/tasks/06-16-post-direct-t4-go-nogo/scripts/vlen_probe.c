#include <stdio.h>

#if defined(__riscv_vector)
#include <riscv_vector.h>
#endif

int main(void) {
#if defined(__riscv_vector)
    printf("__riscv_vector=1\n");
#else
    printf("__riscv_vector=0\n");
#endif

#if defined(__riscv_zvfh)
    printf("__riscv_zvfh=1\n");
#else
    printf("__riscv_zvfh=0\n");
#endif

#if defined(__riscv_vector)
    printf("vlen_bits=%zu\n", __riscv_vlenb() * 8);
#else
    printf("vlen_bits=unavailable\n");
#endif

    return 0;
}
