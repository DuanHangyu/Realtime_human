interface VideoOverlayProps {
  visible: boolean;
}

export function VideoOverlay({ visible }: VideoOverlayProps) {
  if (!visible) return null;
  return (
    <div id="videoOverlay">
      <video
        autoPlay
        muted
        loop
        playsInline
        {...{ 'webkit-playsinline': 'true', 'x5-playsinline': 'true' }}
      >
        <source src="assets/01.mp4" type="video/mp4" />
      </video>
    </div>
  );
}
