/** @type {import('next').NextConfig} */
const nextConfig = {
  // react-leaflet v4 initializes the Leaflet map in an effect and does not
  // survive StrictMode's intentional double-mount in dev, which throws
  // "Map container is already initialized." Disabling StrictMode avoids it;
  // production builds never double-mount regardless.
  reactStrictMode: false,
};

export default nextConfig;
