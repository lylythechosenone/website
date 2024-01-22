---
title: Velvet
github: lylythechosenone/velvet
tags:
    - rust
    - kernel
---

Velvet is the third iteration of my custom kernel. It is built entirely in Rust
(with a bit of inline assembly), and it follows the core principles of speed,
memory efficiency, and simplicity. It aims to be fast with as few compromises as
possible. It is currently in early development, and supports only AArch64[^1].
However, x86_64[^2] support is also planned.

# Philosophy
Velvet is built to be so simple that it can be understood by anyone with a basic
understanding of the architectures. The goal is not to become a large monolithic
kernel, like many of the current ones[^3]. Instead, the kernel should only grow
exactly as much as it needs to in order to function. For this reason, the kernel
itself includes almost no drivers. Currently, the only driver is a dummy UART
driver for use inside of QEMU. Anything else is loaded as a user-space process,
given special access permission to specific parts of the device. This allows for
easier maintenance, as well as more security and transparency for the user, who
has full control over what drivers are used.

It is also built to minimize compromise. Whenever possible, the chosen solution
is one that both uses minimal memory and takes advantage of the speed of modern
hardware. The kernel is built with SMP in mind, and is designed to be able to
scale to as many cores as possible. It is also designed to be able to run on as
little as 1 MiB of RAM (although this is not recommended).

# Why?
In my eyes, there is a lack of innovation in the operating system space. Many
kernels are stuck on old algorithms and designs, reading the old designs and not
bothering to put in the critical thinking required to improve them. In velvet, I
aim to try everything. Many of the algorithms within it are already heavily
customized versions of existing algorithms, and some are entirely original. I
only settle on something when I'm sure that it's the best possible solution.

# Where does it run?
Currently, velvet has only been run in a virtual machine. However, it could
theoretically run on any standard-compliant AArch64 machine. I also plan to add
support for Apple Mac devices, although these are somewhat difficult to support
due to their locked-down ecosystem. Once x86_64 support is added, it will be
runnable on any standard-compliant x86_64 machine without issue.

# When will it be ready?
Velvet is currently in early development, and is not ready for use. However, I
am working on it as much as I can, and I hope to have a usable version ready
within a few years as a maximum.

[^1]: ARMv8 64-bit Architecture, often used in mobile devices. Also present in
    newer Apple Mac and Microsoft Surface devices. Sometimes present in
    Chromebooks and the like. [Wikipedia](https://en.wikipedia.org/wiki/AArch64)

[^2]: x86 64-bit Architecture, also known as AMD64. Present in many desktops and
    laptops around the world. [Wikipedia](https://en.wikipedia.org/wiki/X86-64)

[^3]: The Linux kernel has a source of about 245 MiB at the time of writing
    (commit 7a396820222d6d4c02057f41658b162bdcdadd0e). XNU, the kernel that
    powers MacOS, has a source of about 17MiB (xnu-10002.1.13), excluding
    drivers, which likely make up a large amount of the source. The actual size
    of the Windows kernel is unknown, but it is rumored to be much larger than
    both of these.

*[SMP]: Symmetric Multi-Processing
