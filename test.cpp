#include <iostream>
#include <array>
#include <vector>
#include <ranges>
#include <chrono>
#include <typeinfo>  //for 'typeid' to work  
using namespace std::chrono;
const int MAP_MAX_RADIUS = 5;
class HexagonalCoordinates{
    public:
    int x;
    int y;
    int z;
    explicit HexagonalCoordinates(int xx,int yy):
     x(xx),y(yy),z(-xx-yy){
     }
};
auto get_new_hexagon(const HexagonalCoordinates & coord,const HexagonalCoordinates & offset){
    return HexagonalCoordinates(coord.x+offset.x,coord.y+offset.y);
}
const std::array<const HexagonalCoordinates, 6> neighboursOffsets = {
    HexagonalCoordinates(1, 0),
    HexagonalCoordinates(-1, 0),
    HexagonalCoordinates(0, 1),
    HexagonalCoordinates(0, -1),
    HexagonalCoordinates(-1, 1),
    HexagonalCoordinates(1, -1)
};

auto hexagonal_neighbors(const HexagonalCoordinates &coords){
    auto inMap = [](const HexagonalCoordinates & new_coord) { return new_coord.x<= MAP_MAX_RADIUS && new_coord.x>= -MAP_MAX_RADIUS&& new_coord.y<=MAP_MAX_RADIUS && new_coord.y>=-MAP_MAX_RADIUS;};
    auto offset = [&coords](const HexagonalCoordinates & offset){return HexagonalCoordinates(coords.x+offset.x,coords.y+offset.y);};
    return neighboursOffsets | std::views::filter(inMap);


}


int main()
{
    HexagonalCoordinates first(0,0);
    // to prevent lazy loading
    auto result(hexagonal_neighbors(HexagonalCoordinates(0,1)));
    auto start = high_resolution_clock::now();
    for (long long i=0; i<100'000; ++i){
        result=(hexagonal_neighbors(first));
    }
    auto stop = high_resolution_clock::now();
    auto duration = duration_cast<microseconds>(stop - start);
     std::cout << "Time taken by function: "
         << duration.count() << " microseconds" << std::endl;
    for(const auto& x: result){
        std::cout<<x.x<<" "<<x.y<<" "<<x.z<<std::endl;
    }
    return 0;
}