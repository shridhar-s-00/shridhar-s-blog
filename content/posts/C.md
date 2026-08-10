---
Title: I'm writing a dynamic list in C. (Sort of)
Date: 2026-08-10
Summary: I'm writing a list that can store any generic value. I'm doing this to learn structs, unions, pointers, generic programming and some basic DSA.
---

# Version 1
```C
#include <stdint.h>
#include<stdio.h>
#include<stdlib.h>
#include<math.h>

/*
 * Build instructions:
 * clang -std=c17 lists.c -o -lm lists && ./lists //Dangit, the lm flag comes AFTER lists, not before it
 *                           ^^^ This meant that -lm was the name of the output file. This is a confusion between compiler flags and output flags
 * clang -std=c23 -Wall -Werror lists.c -o lists -lm && ./lists //This is correct
 */

typedef enum {NODETYPE_I64, NODETYPE_F64, NODETYPE_STR} node_type;

char* stringify_node_type(node_type t){
    if (t==NODETYPE_F64) return "64-bit FLOAT";
    if (t==NODETYPE_I64) return "64-bit INT";
    if (t==NODETYPE_STR) return "STRING";

    return "UNKNOWN TYPE";
}

typedef union data{
    int64_t data_i64;
    double  data_f64;
    char*   data_str;
}data;

typedef struct node{
    data value;
    struct node* next;
    node_type type;
} __attribute__((packed)) node; //the attribute allows me to reduce the size of the struct by removing the padding on unsigned char

void print_node(node n){
    if      (n.type==NODETYPE_F64) printf("Data stored in node: %lf\n", n.value.data_f64);
    else if (n.type==NODETYPE_I64) printf("Data stored in node: %lld\n", n.value.data_i64);
    else if (n.type==NODETYPE_STR) printf("Data stored in node: %s\n", n.value.data_str);
    else                           printf("Data stored in node: %lf (ERROR VALUE)\n", n.value.data_f64);
    printf("Next node: %p\n", n.next);
    printf("Type of node: %s\n\n", stringify_node_type(n.type));
}

node update_node(int64_t value_i, double value_d, char* value_s, node* next_node, node_type new_type){
    data d;
    if (new_type==NODETYPE_F64) d.data_f64= value_d;
    else if (new_type==NODETYPE_I64) d.data_i64= value_i;
    else if (new_type==NODETYPE_STR) d.data_str= value_s;
    else{
        d.data_f64= NAN;
        new_type= NODETYPE_F64;
    }
    node result= {d, next_node, new_type};
    return result;
}

int main(){
    data x;
    x.data_f64= M_PI;
    node n= {x, (node*)(0), NODETYPE_F64};
    print_node(n);
    n= update_node(0, 0, "GOODBYE", (node*)(0), 9);
    print_node(n);
    return 0;
}
```

This was a prototype I hacked together super quickly. It needs a lot of improvements. For a start, I don't like how the function update_node() works.

```C
node update_node(int64_t value_i, double value_d, char* value_s, node* next_node, node_type new_type)
//               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
// Here, I'm wasting a lot of parameters by passing the i64, f64 and strings separately. I can do better than that by passing a void pointer and a type.
```
