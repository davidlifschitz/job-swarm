cask "ml-job-swarm" do
  version "0.2.0"
  sha256 "4ad7087312a36175b216ff66ebebfbc3e62dc25f926c3c204ac302f0eaeba2e1"

  url "https://github.com/davidlifschitz/job-swarm/releases/download/v#{version}/MLJobSwarm-#{version}-macos-arm64.tar.gz"
  name "ML Job Swarm"
  desc "Local-first job catalog and resume matching for curated technical roles"
  homepage "https://github.com/davidlifschitz/job-swarm"

  depends_on macos: :sonoma
  depends_on arch: :arm64

  app "MLJobSwarm.app"

  postflight do
    system_command "/usr/bin/xattr", args: ["-cr", "#{appdir}/MLJobSwarm.app"]
    system_command "/usr/bin/codesign", args: ["--force", "--deep", "--sign", "-", "#{appdir}/MLJobSwarm.app"]
  end

  zap trash: [
    "~/Library/Application Support/MLJobSwarm",
  ]
end