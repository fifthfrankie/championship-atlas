{
  description = "Championship Atlas development environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "aarch64-darwin" "x86_64-darwin" "x86_64-linux" "aarch64-linux" ];
      forAll = f: nixpkgs.lib.genAttrs systems (s: f nixpkgs.legacyPackages.${s});
    in {
      devShells = forAll (pkgs: {
        default = pkgs.mkShell {
          packages = [ pkgs.python3 pkgs.nodejs_22 pkgs.gnumake pkgs.sqlite pkgs.playwright-driver.browsers ];
          # The npm `playwright` version in site/package.json must equal playwright-driver's version,
          # because Playwright looks for the browser build that matches its own release.
          PLAYWRIGHT_BROWSERS_PATH = "${pkgs.playwright-driver.browsers}";
          PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS = "true";
          PLAYWRIGHT_DRIVER_VERSION = pkgs.playwright-driver.version;
          # Fail loudly, not at browser launch, if the npm package and the Nix browser drift apart.
          shellHook = ''
            if [ -f site/node_modules/playwright/package.json ]; then
              have=$(node -p "require('./site/node_modules/playwright/package.json').version")
              if [ "$have" != "$PLAYWRIGHT_DRIVER_VERSION" ]; then
                echo "WARNING: site playwright $have does not match the Nix browser build $PLAYWRIGHT_DRIVER_VERSION." >&2
                echo "         Set playwright to exactly $PLAYWRIGHT_DRIVER_VERSION in site/package.json and run npm install." >&2
              fi
            fi
          '';
        };
      });
    };
}
