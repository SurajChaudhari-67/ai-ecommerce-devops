#!/usr/bin/env python3
"""AI-assisted incident analysis for Nexvion.

Reads logs from a file or from Elasticsearch, then reports:
error classification, severity, possible root cause, suggested remediation.
Default engine is rule-based. Optional: --llm ollama for an extra AI summary.
Uses only the Python standard library.
"""
import argparse
import json
import re
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone

SEV_ORDER = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

RULES = [
    {
        "name": "Database connection timeout",
        "pattern": r"(database|db|postgres|mysql|mongo).*(timeout|timed out|refused)",
        "category": "Database",
        "severity": "HIGH",
        "cause": "Database connectivity or configuration issue",
        "steps": ["Check database availability", "Check network connectivity (service/DNS/ports)",
                  "Verify credentials in the Kubernetes Secret", "Check connection limits and pool size"],
    },
    {
        "name": "Database connection limit reached",
        "pattern": r"remaining connection slots|too many connections",
        "category": "Database",
        "severity": "CRITICAL",
        "cause": "Database has run out of connection slots",
        "steps": ["Close idle connections", "Increase max_connections or use a pool",
                  "Check for connection leaks in the application"],
    },
    {
        "name": "Upstream / bad gateway error",
        "pattern": r"connect\(\) failed .* upstream|upstream (timed out|prematurely closed)|\" 50[234] ",
        "category": "Networking",
        "severity": "HIGH",
        "cause": "Backend service is down, restarting or unreachable",
        "steps": ["Check pod status: kubectl get pods -n nexvion", "Check service endpoints: kubectl get endpoints",
                  "Review readiness probe and recent rollouts", "Check backend logs"],
    },
    {
        "name": "Container crash loop",
        "pattern": r"back-off restarting failed container|crashloopbackoff",
        "category": "Kubernetes",
        "severity": "HIGH",
        "cause": "Container keeps crashing at startup or runtime",
        "steps": ["kubectl logs --previous <pod>", "kubectl describe pod <pod>",
                  "Check config, environment variables and probes", "Roll back: helm rollback nexvion"],
    },
    {
        "name": "Image pull failure",
        "pattern": r"errimagepull|imagepullbackoff|failed to pull image",
        "category": "Deployment",
        "severity": "MEDIUM",
        "cause": "Image tag missing in registry or AKS lacks pull permission",
        "steps": ["Verify the tag exists in ACR: az acr repository show-tags",
                  "Check AcrPull role: az aks update --attach-acr", "Check image name and tag in values.yaml"],
    },
    {
        "name": "Out of memory (OOMKilled)",
        "pattern": r"oomkilled|out of memory|exitcode=137",
        "category": "Resources",
        "severity": "HIGH",
        "cause": "Container exceeded its memory limit",
        "steps": ["Check usage: kubectl top pods", "Increase the memory limit in values.yaml",
                  "Look for memory leaks or traffic spikes"],
    },
    {
        "name": "Disk full",
        "pattern": r"no space left on device|disk (is )?full",
        "category": "Infrastructure",
        "severity": "CRITICAL",
        "cause": "Node or volume has no free disk space",
        "steps": ["Check usage: df -h", "Clean old images/logs (scripts/cleanup.sh)",
                  "Increase disk size or PVC size"],
    },
    {
        "name": "DNS resolution failure",
        "pattern": r"no such host|could not resolve|name or service not known",
        "category": "Networking",
        "severity": "MEDIUM",
        "cause": "Service name does not resolve (wrong name or CoreDNS issue)",
        "steps": ["Verify the service name and namespace", "Check CoreDNS pods in kube-system",
                  "Test: kubectl run -it --rm dns --image=busybox -- nslookup <name>"],
    },
    {
        "name": "Access denied (403/401)",
        "pattern": r"\" 40[13] |permission denied|unauthorized|forbidden",
        "category": "Security",
        "severity": "MEDIUM",
        "cause": "Missing permission, bad credentials or probing of protected paths",
        "steps": ["Check source IP and request pattern for abuse", "Verify RBAC and credentials",
                  "Consider rate limiting on the ingress"],
    },
    {
        "name": "Server error (HTTP 5xx)",
        "pattern": r"\" 50[01] ",
        "category": "Application",
        "severity": "HIGH",
        "cause": "Application raised an internal error",
        "steps": ["Check application logs around the timestamp", "Check recent deployments",
                  "Roll back if it started after a release"],
    },
    {
        "name": "Not found (HTTP 404)",
        "pattern": r"\" 404 ",
        "category": "Application",
        "severity": "LOW",
        "cause": "Requests for missing files or routes (broken link or scanning)",
        "steps": ["Check for broken links in the frontend", "Ignore if it is random bot traffic"],
    },
]


def fetch_from_es(es_url, index, size, minutes):
    body = {
        "size": size,
        "sort": [{"@timestamp": "desc"}],
        "query": {"range": {"@timestamp": {"gte": "now-%dm" % minutes}}},
        "_source": ["message"],
    }
    req = urllib.request.Request(
        "%s/%s/_search" % (es_url.rstrip("/"), index),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.load(resp)
    return [h["_source"].get("message", "") for h in data["hits"]["hits"]]


def analyze(lines):
    compiled = [(r, re.compile(r["pattern"], re.I)) for r in RULES]
    counts, examples = Counter(), {}
    for line in lines:
        for rule, rx in compiled:
            if rx.search(line):
                counts[rule["name"]] += 1
                examples.setdefault(rule["name"], line.strip()[:160])
                break
    findings = []
    for rule in RULES:
        if rule["name"] in counts:
            findings.append({
                "issue": rule["name"], "category": rule["category"], "severity": rule["severity"],
                "occurrences": counts[rule["name"]], "possible_root_cause": rule["cause"],
                "suggested_investigation": rule["steps"], "example": examples[rule["name"]],
            })
    findings.sort(key=lambda f: (-SEV_ORDER[f["severity"]], -f["occurrences"]))
    return findings


def llm_summary(findings, model):
    prompt = ("You are a DevOps assistant. In 5 short lines, summarize these incidents "
              "and the most urgent next action:\n" + json.dumps(findings, indent=1))
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps({"model": model, "prompt": prompt, "stream": False}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.load(resp).get("response", "").strip()


def main():
    p = argparse.ArgumentParser(description="Nexvion AI-assisted incident analysis")
    p.add_argument("--file", help="read logs from a text file")
    p.add_argument("--es", help="Elasticsearch URL, e.g. http://localhost:9200")
    p.add_argument("--index", default="filebeat-*")
    p.add_argument("--minutes", type=int, default=60)
    p.add_argument("--size", type=int, default=500)
    p.add_argument("--llm", choices=["ollama"], help="add an AI summary using a local Ollama model")
    p.add_argument("--model", default="llama3.2:3b")
    p.add_argument("--out", default="incident_report.json")
    a = p.parse_args()

    if a.file:
        with open(a.file, encoding="utf-8", errors="ignore") as f:
            lines = f.read().splitlines()
    elif a.es:
        lines = fetch_from_es(a.es, a.index, a.size, a.minutes)
    else:
        sys.exit("Give --file or --es")

    findings = analyze(lines)
    top = findings[0]["severity"] if findings else "NONE"
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lines_analyzed": len(lines),
        "overall_severity": top,
        "findings": findings,
    }

    print("=" * 62)
    print("INCIDENT ANALYSIS REPORT  |  lines: %d  |  overall severity: %s" % (len(lines), top))
    print("=" * 62)
    if not findings:
        print("No known error patterns found. System looks healthy.")
    for i, f in enumerate(findings, 1):
        print("\n[%d] %s  (%s, %s, x%d)" % (i, f["issue"], f["category"], f["severity"], f["occurrences"]))
        print("    Possible root cause : %s" % f["possible_root_cause"])
        print("    Example log         : %s" % f["example"])
        print("    Suggested investigation / remediation:")
        for s in f["suggested_investigation"]:
            print("      - %s" % s)

    if a.llm and findings:
        try:
            summary = llm_summary(findings, a.model)
            report["llm_summary"] = summary
            print("\n--- AI summary (%s) ---\n%s" % (a.model, summary))
        except Exception as e:
            print("\n(LLM summary skipped: %s)" % e)

    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("\nJSON report saved to %s" % a.out)


if __name__ == "__main__":
    main()
