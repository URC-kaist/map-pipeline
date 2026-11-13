// Read a generated YAML with the installed Nav2 library; no node or robot launch.
#include <fstream>
#include <iostream>
#include <nav2_map_server/map_io.hpp>

int main(int argc, char ** argv) {
  if (argc != 3) return 2;
  nav_msgs::msg::OccupancyGrid grid;
  auto status = nav2_map_server::loadMapFromYaml(argv[1], grid);
  if (status != nav2_map_server::LOAD_MAP_SUCCESS) return 3;
  std::ofstream out(argv[2], std::ios::binary);
  out.write(reinterpret_cast<const char *>(grid.data.data()), grid.data.size());
  if (!out) return 4;
  std::cout << grid.info.width << " " << grid.info.height << " "
            << grid.info.resolution << "\n";
}
