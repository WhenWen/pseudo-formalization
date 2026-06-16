import http.server, socketserver, sys
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 41665
class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache"); self.send_header("Expires", "0")
        super().end_headers()
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("0.0.0.0", PORT), H) as httpd:
    print(f"serving (no-cache) on :{PORT}"); httpd.serve_forever()
