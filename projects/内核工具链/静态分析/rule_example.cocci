// Coccinelle example rule: suggest kcalloc for multiplications in kmalloc
@@
expression count, size;
identifier T;
@@
- T *ptr = kmalloc(count * size, GFP_KERNEL);
+ T *ptr = kcalloc(count, size, GFP_KERNEL);

