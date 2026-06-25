# Job-Search AI Agent — The Plain-English Guide

## What this is

This is a free job-search helper that runs **on your own computer**. You give it your resume and a list of job openings. It reads them and hands back three things:

1. **The 25 jobs that fit you best**, sorted with the best matches on top.
2. **10 ways to improve your resume**, each tied to what real job postings ask for.
3. **5 skills you're missing** that employers want — plus free ways to learn each one.

It then saves all of this to a spreadsheet and can email you a fresh batch every weekday morning.

## Why you might want it

Most job tools send your resume off to a company's website. This one is different: **everything stays on your computer.** Your resume and your searches never leave your machine and never go to the cloud. Nothing is uploaded, and you don't pay for anything.

It also does the tedious part for you — reading dozens of job posts, spotting patterns, and telling you exactly where your resume falls short.

## The one idea that makes this work: a "local AI"

This tool uses **AI** (artificial intelligence — a computer program that can read and write like a person). Normally, AI like this runs on giant company servers on the internet. This tool runs a smaller version of that AI **right on your own computer instead.**

Think of it like the difference between calling a big call center and asking a smart friend who's sitting in your living room. The friend isn't as huge as the call center, but they're private, they're free, and they never share what you tell them.

Because it runs on your computer, **the tool picks the right size of AI for your machine automatically.** You don't choose anything:

- A normal laptop gets a smaller, faster AI.
- A computer with a strong graphics card (the extra chip that powers games and video) gets a smarter one.

Either way, it just works. The better your computer, the smarter the help — automatically.

## What you need before you start

1. **A computer** — Windows, Mac, or Linux.
2. **A free program called Docker.** Think of Docker as a self-contained box that holds the whole tool and runs it for you, so you don't have to install a dozen pieces by hand. [Download it here](https://www.docker.com/products/docker-desktop/), install it, and open it once so it's running. You'll see a small whale icon near your clock.

That's it. You don't need to be technical, and you won't have to fix anything by hand.

## How to set it up (copy and paste, one line at a time)

Open a terminal — a plain text window where you type commands:

- **Windows:** search your Start menu for "PowerShell."
- **Mac:** search for "Terminal."

Then paste each line below and press Enter after each one:

```bash
git clone https://github.com/PWDevens/job-search-ai-agent.git
cd job-search-ai-agent
cp .env.example .env
docker compose up -d
```

The first time, this takes **5 to 15 minutes.** It's downloading the tool and the AI. That's normal — go grab a coffee. ☕

### Download the AI "brain" (one time)

Paste this and wait. It grabs the AI that fits your computer:

```bash
docker compose exec ollama ollama pull phi4-mini
```

If your computer has a strong graphics card, also run this one:

```bash
docker compose exec ollama ollama pull llama3.1:8b
```

### Load some sample data so you can try it right away

```bash
docker compose exec app python scripts/ingest_jobs.py data/demo/demo_jobs.csv
docker compose exec app python scripts/ingest_resume.py data/demo/demo_resume.txt
```

### Open it

Open your web browser and go to: **http://localhost:5000**

Type a job title, upload your resume (PDF or Word), and click search. Done!

### When you're finished

Type this to shut it down. Your data is saved:

```bash
docker compose down
```

Next time, just run `docker compose up -d` again. You won't have to download anything twice.

## What you put in

**Your resume** — a PDF, a Word document, or a plain text file. A PDF you can highlight text in works best. (A scanned image of a resume won't work, because there's no real text in it for the tool to read.)

**A list of jobs** — a spreadsheet or CSV file. A CSV is just a simple table saved as plain text. It needs at least three columns: the job **title**, the **company**, and a **description**. You can also include the location, pay, and a link if you have them.

## What you get back

- **Top job matches**, ranked by how closely they fit your background.
- **Resume tips** that point to real wording in real job posts — not generic advice.
- **Skill gaps**: skills that show up again and again in the jobs you want but are missing from your resume, with a free or cheap way to learn each one.

You see all of this on a clean web page. It's also saved to a spreadsheet you can keep, and it can be emailed to you every weekday at 8 in the morning if you set that up.

## Want the weekday emails?

You can have a summary sent to your inbox every weekday morning. To turn this on, you give the tool permission to send email through your Gmail account. This uses a special one-time "app password" from Google (not your real password), so it stays secure. The setup is a few clicks in your Google account settings.

## If something goes wrong

Here are the most common hiccups and the fix for each.

**The tool says it can't find the AI model.**
It hasn't finished downloading. Run this and wait:
```bash
docker compose exec ollama ollama pull phi4-mini
```

**No jobs show up after you search.**
You probably haven't loaded any jobs yet. Load the sample jobs:
```bash
docker compose exec app python scripts/ingest_jobs.py data/demo/demo_jobs.csv
```

**Your resume won't upload.**
Use a PDF you can select text in, a Word file, or a plain text file. A scanned picture of a resume won't work — save it as a real PDF or text file instead.

**It feels slow.**
On a regular laptop, each search takes about 10 to 20 seconds. That's expected. A computer with a strong graphics card is about twice as fast, and the tool switches to the faster AI on its own.

**It says "too many searches."**
The tool limits you to 10 searches a minute to keep things stable. Wait a minute and try again.

## Is my information safe?

Yes. A few things to know:

- Your resume and searches **stay on your computer.** Nothing is sent to the internet.
- Your resume text is **never written into the tool's logs** — only a scrambled fingerprint of it is kept, which can't be turned back into your resume.
- The tool checks the files you upload to make sure nothing harmful sneaks in.

## In one sentence

Upload your resume, point it at some job listings, and this free, private tool tells you which jobs fit, how to sharpen your resume, and which skills to learn next — all without your information ever leaving your computer.

---

*Want the full technical version, with the setup details for developers? See [README.md](README.md).*
