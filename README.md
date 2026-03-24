# Grace Hopper Egress Monitor

See if there is a way to log all OUTBOUND connections from the Grace Hopper server.
Does UFW have logging?  (Yes, but Rocky Linux uses firewalld.)
Log - even if the connection is permitted.
Motivation -> are Ollama LLMs doing something undocumented?
We should log successful and unsuccessful outbound connections.
Even if the outbound is blocked, we should know an attempt was made.

Solution — bash script to set up logging, and Python script to parse the logs, using color.
