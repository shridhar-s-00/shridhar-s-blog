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

## Trying alternatives
**Void Pointers:**  

- This one is an improvement in that it drops all the redundancies and just pass 3 values instead of every single type and then the next node and type.  
- The downside is that actually passing in values is a pain and I have found out `(void*)&(int64_t){INT_MAX}` is a temporary variable, not a constant. Basically, you kind of just have to create pointers to temporary variables using this crap method. Strings don't require this though, so thats fine. You learn something new everyday.  

**Making separate functions for every single type:**  

- I have a strong preferance for this, but I've already written code and I'm too lazy to modify it.
- Even when writing multiple functions for each type, you run into issues of how do you implement them. Do you make the function I've created in [Version 1](C) call all the separate implementations, or do you wrap this into a bunch of different functions so that each one is typesafe by itself? I certainly didn't know what to do, but each ones a lot of work. I'm starting to understand why people really really wanted templates in C++.  

**Use a preprocessor Macro:**  

- I have looked at that implementation and I just, don't like it.
- Its the easiest solution of the bunch implementation-wise but the trick was to basically replace your function call with a modified function call using `#define`.
- Theres also a version that uses generics in C along with the preprocessor. I can't begin to understand what I'm looking at so I'll give it some time.  

**Write a common logic core thats different to what I wrote:**  

- This one is basically wrapping my struct around a struct with a second field to store a boolean for validity checking.
- Then you proceed to write type-safe macros or functions.
- I just thought this was a lot of boilerplate code, but its all about tradeoffs here.  

**Just passing the union dirrectly:**  

- Just passing the union directly would've been the easiest option because the user would've done the typechecking and hopefully wrote the types along with it properly.
- The idea is that the struct that stores the data should look like this:
```C
typedef struct {
    node_type type;
    union {
        int64_t i64;
        double f64;
        char* str;
    } value;
} node_value;
```
- Then, you can declare the variables like new nodes like so: `node n= create_node((node_value){.type = NODETYPE_STR, .value.str = "hello"}, NULL);`
- I'll probably write it like this going forward, but this is just practice, not a design/review lesson. I'll stick to the `(void*) value` method for now.
