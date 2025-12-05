import http from "http"
import url from "url"
const srv=http.createServer((req,res)=>{
  const u=url.parse(req.url,true)
  if(req.method==="GET"&&u.pathname==="/describe"){
    const rtsp=u.query.path||"rtsp://vendor-cam.test/ok"
    const sdp=[
      "v=0",
      "o=- 0 0 IN IP4 127.0.0.1",
      "s=HopSec Asylumn Test Stream",
      "t=0 0",
      "a=control:*",
      "m=video 0 RTP/AVP 96",
      "a=rtpmap:96 H264/90000",
      "a=fmtp:96 packetization-mode=1",
      "a=x-job-metadata: {\"SIM_EXEC\": true, \"note\": \"diagnostics\"}"
    ].join("\r\n")+"\r\n"
    res.writeHead(200,{"Content-Type":"application/sdp"})
    res.end(sdp)
    return
  }
  res.writeHead(404);res.end()
})
srv.listen(13403,"0.0.0.0")
