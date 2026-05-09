interface PosterScreenProps {
  visible: boolean;
}

export function PosterScreen({ visible }: PosterScreenProps) {
  if (!visible) return null;
  return <div className="poster"></div>;
}
