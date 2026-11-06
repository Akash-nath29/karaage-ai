"""SYNTHETIC question paper for testing question extraction (PRD H3). Not a real university exam.

Written for SemSaviour because no previous-year papers were available (docs/decisions.md M14, user on 2026-11-06:
"build on your own"). It follows the common Indian B.Tech semester format (MCQ group, short and long answer groups,
"OR" alternatives, multi-part questions, "short notes") and the AM401 Operating System syllabus in
test_material/AIML-R23.pdf, so extraction and topic mapping can be measured against known answers.

EXPECTED lists every question a student could answer: label, marks, acceptable types, syllabus topic, page.
"""

import pymupdf

TITLE = "SYNTHETIC SAMPLE PAPER - written for SemSaviour testing, not a real university examination"

PAGES = [
    f"""{TITLE}

B.Tech (CSE - AI & ML) Semester Examination
Operating System (AM401)
Time Allotted: 3 Hours                                                  Full Marks: 70
The figures in the margin indicate full marks. Candidates are required to give their answers in their own words.

GROUP - A (Multiple Choice Type Questions)
1. Answer any ten of the following:                                     10 x 1 = 10

(i) Which of the following is NOT a necessary condition for deadlock?
    (a) Mutual exclusion  (b) Hold and wait  (c) Preemption  (d) Circular wait
(ii) Which of these is NOT stored in a Process Control Block?
    (a) Program counter  (b) CPU registers  (c) Process state  (d) Compiler version
(iii) Belady's anomaly can occur with which page replacement algorithm?
    (a) LRU  (b) FIFO  (c) Optimal  (d) None of these
(iv) Round robin scheduling with a very large time quantum behaves like
    (a) SJF  (b) Priority  (c) FCFS  (d) Multilevel queue
(v) A translation look-aside buffer (TLB) is used to
    (a) speed up address translation  (b) store page tables on disk  (c) schedule processes  (d) manage free space
(vi) Fill in the blank: The ________ disk scheduling algorithm moves the head to one end servicing requests,
    then returns to the other end without servicing requests on the return trip.
(vii) State True or False: User-level threads are scheduled directly by the kernel.
(viii) Fill in the blank: A semaphore whose value is restricted to 0 and 1 is called a ________ semaphore.
(ix) Which file allocation method suffers from external fragmentation?
    (a) Contiguous  (b) Linked  (c) Indexed  (d) None of these
(x) Fill in the blank: DMA stands for ________ .
(xi) Which type of operating system must respond within strict time constraints?
    (a) Batch  (b) Real-time  (c) Time-sharing  (d) Distributed
(xii) The number of processes completed per unit time is called
    (a) Turnaround time  (b) Waiting time  (c) Throughput  (d) Response time
""",
    f"""{TITLE}

GROUP - B (Short Answer Type Questions)
Answer any three of the following.                                      3 x 5 = 15

2. Explain the different states of a process with a neat state transition diagram.              5
3. Differentiate between paging and segmentation.                                                 5
4. What is the critical section problem? State the three requirements that any solution
   to it must satisfy.                                                                            5
5. Explain the role of an operating system as a resource manager.                                 5
6. Compare user-level threads and kernel-level threads.                                           5
                                    OR
   Explain the many-to-one, one-to-one and many-to-many multithreading models.                    5

GROUP - C (Long Answer Type Questions)
Answer any three of the following.                                      3 x 15 = 45

7. (a) Consider four processes with the following arrival and burst times (in ms):
       P1: arrival 0, burst 8;  P2: arrival 1, burst 4;  P3: arrival 2, burst 9;  P4: arrival 3, burst 5.
       Draw the Gantt charts for FCFS, non-preemptive SJF and Round Robin (time quantum = 2 ms),
       and calculate the average waiting time for each.                                          10
   (b) Define turnaround time and response time.                                                   5
8. (a) A system has five processes P0 to P4 and three resource types A, B and C with 10, 5 and 7
       instances. Using the Banker's algorithm with the given Allocation and Max matrices,
       determine whether the system is in a safe state and find a safe sequence.
       Allocation: P0 (0 1 0), P1 (2 0 0), P2 (3 0 2), P3 (2 1 1), P4 (0 0 2)
       Max:        P0 (7 5 3), P1 (3 2 2), P2 (9 0 2), P3 (2 2 2), P4 (4 3 3)                    10
   (b) Describe the methods a system can use to recover from a deadlock.                           5
""",
    f"""{TITLE}

9. (a) For the page reference string 7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2 and three frames, find the
       number of page faults using FIFO, LRU and Optimal page replacement.                         9
   (b) What is thrashing? How does the working-set model help to prevent it?                       6
10. (a) A disk has 200 cylinders numbered 0 to 199. The head is at cylinder 53 and the request queue is
       98, 183, 37, 122, 14, 124, 65, 67. Calculate the total head movement (in cylinders) using SSTF.   8
    (b) Explain the indexed allocation method of a file system with a suitable diagram.             7
11. Write short notes on any three of the following:                                         3 x 5
    (a) Interrupts versus polling
    (b) The dining philosophers problem
    (c) Monitors
    (d) Batch versus time-sharing operating systems
    (e) Free-space management using a bit vector

                                        ----------
""",
]

OBJ = {"mcq"}
FILL = {"fill_blank"}
SHORT_OR_LONG = {"short", "long", "descriptive"}

EXPECTED = [
    # (label, marks, acceptable types, topic, page, distinctive words for matching)
    ("1(i)", 1, OBJ, "Deadlocks", 1, "necessary condition for deadlock"),
    ("1(ii)", 1, OBJ, "Processes", 1, "process control block"),
    ("1(iii)", 1, OBJ, "Virtual Memory", 1, "belady anomaly page replacement"),
    ("1(iv)", 1, OBJ, "CPU Scheduling", 1, "round robin large time quantum"),
    ("1(v)", 1, OBJ, "Memory Allocation", 1, "translation look-aside buffer"),
    ("1(vi)", 1, FILL, "Disk Management", 1, "disk scheduling algorithm moves the head"),
    ("1(vii)", 1, {"true_false"}, "Threads", 1, "user-level threads scheduled by the kernel"),
    ("1(viii)", 1, FILL, "Process Synchronization", 1, "semaphore restricted to 0 and 1"),
    ("1(ix)", 1, OBJ, "File Systems", 1, "file allocation external fragmentation"),
    ("1(x)", 1, FILL, "I/O Systems", 1, "DMA stands for"),
    ("1(xi)", 1, OBJ, "Types of Operating Systems", 1, "strict time constraints"),
    ("1(xii)", 1, OBJ, "CPU Scheduling", 1, "processes completed per unit time"),
    ("2", 5, SHORT_OR_LONG, "Processes", 2, "states of a process state transition diagram"),
    ("3", 5, SHORT_OR_LONG, "Memory Allocation", 2, "paging and segmentation"),
    ("4", 5, SHORT_OR_LONG, "Process Synchronization", 2, "critical section problem requirements"),
    ("5", 5, SHORT_OR_LONG, "OS Fundamentals", 2, "operating system as a resource manager"),
    ("6", 5, SHORT_OR_LONG, "Threads", 2, "compare user-level threads and kernel-level threads"),
    ("6 OR", 5, SHORT_OR_LONG, "Threads", 2, "many-to-one one-to-one many-to-many multithreading models"),
    ("7(a)", 10, SHORT_OR_LONG | {"numerical"}, "CPU Scheduling", 2, "gantt charts fcfs sjf round robin average waiting"),
    ("7(b)", 5, SHORT_OR_LONG, "CPU Scheduling", 2, "define turnaround time and response time"),
    ("8(a)", 10, SHORT_OR_LONG | {"numerical"}, "Deadlocks", 2, "banker's algorithm safe state safe sequence"),
    ("8(b)", 5, SHORT_OR_LONG, "Deadlocks", 2, "recover from a deadlock"),
    ("9(a)", 9, SHORT_OR_LONG | {"numerical"}, "Virtual Memory", 3, "page faults fifo lru optimal"),
    ("9(b)", 6, SHORT_OR_LONG, "Virtual Memory", 3, "thrashing working-set model"),
    ("10(a)", 8, {"numerical"} | SHORT_OR_LONG, "Disk Management", 3, "total head movement sstf"),
    ("10(b)", 7, SHORT_OR_LONG, "File Systems", 3, "indexed allocation method"),
    ("11(a)", 5, SHORT_OR_LONG, "I/O Systems", 3, "interrupts versus polling"),
    ("11(b)", 5, SHORT_OR_LONG, "Process Synchronization", 3, "dining philosophers problem"),
    ("11(c)", 5, SHORT_OR_LONG, "Process Synchronization", 3, "monitors"),
    ("11(d)", 5, SHORT_OR_LONG, "Types of Operating Systems", 3, "batch versus time-sharing"),
    ("11(e)", 5, SHORT_OR_LONG, "File Systems", 3, "free-space management bit vector"),
]


def pdf_bytes() -> bytes:
    doc = pymupdf.open()
    for text in PAGES:
        page = doc.new_page()
        left = page.insert_textbox(pymupdf.Rect(36, 36, 576, 806), text, fontsize=8.5, fontname="cour")
        assert left >= 0, f"page text overflows by {-left:.0f} pt"
    return doc.tobytes()


if __name__ == "__main__":
    from pathlib import Path

    out = Path(__file__).with_name("SYNTHETIC_os_question_paper.pdf")
    out.write_bytes(pdf_bytes())
    print(f"wrote {out} ({len(EXPECTED)} expected questions)")
