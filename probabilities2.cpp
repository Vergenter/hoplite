
#include <iostream>
#include <array>
#include <random>
#include <algorithm>

struct Result{
    std::size_t _000111;
    std::size_t _010110;
    std::size_t _100110;
    std::size_t _100101;
    Result():_000111(0),_010110(0),_100110(0),_100101(0){}
};

const std::size_t TRIALS = 10'000'000;
Result test(){
    auto result = Result();
    std::random_device r;
    std::default_random_engine e1(r());
    std::uniform_int_distribution<std::size_t> moves_gen(0, 1);
    for( std::size_t i=0;i<TRIALS;++i){
        std::array<std::size_t,3> order{0,1,2};
        std::shuffle(order.begin(), order.end(), e1);
        auto moves = moves_gen(e1);
        auto moves_2 =  moves_gen(e1);
        if (order[0]==0){ // X11 000
            if (order[1]==1){ // 0X1 100
                result._000111 +=1;
            } else { // 01X 100
                if (moves == 0){ // 010 110
                    result._010110 +=1;
                } else { // 010 101
                    result._000111 +=1;
                }
            }      
        } else if( order[0]==1){ // 1X1 000
            if (moves ==0){ // 101 100
                if (moves_2 ==0){ // 10X 100
                    result._100110 +=1;
                } else { // 10X 100
                    result._100101 +=1;
                } 
            } else { // 101 010
                result._000111 +=1;
            }
        } else { // 11X 000
            if (moves ==0){ // 110 010
                if (order[1]==0){ // X10 010
                    result._010110 +=1;
                } else { // 1X0 010
                    result._100110 +=1;
                }
            } else {  // 110 001
                if (order[1]==0){ // X10 001
                    result._000111 +=1;
                } else { // 1X0 001
                    if (moves_2==0){ // 100 101
                        result._100101 +=1;
                    } else { // 100 011
                        result._000111 +=1;
                    }
                }
            }
        }

    }
    return result;


}


// orders = numpy.random.randint(3, size=TRIALS)
// orders_2 = numpy.random.randint(2, size=TRIALS)
// moves = numpy.random.randint(2, size=TRIALS)
// moves_2 = numpy.random.randint(2, size=TRIALS)

// @numba.njit
// def test():
//     count = {"000111":0,"010110":0,"100110":0,"100101":0}
//     for i in numba.prange(TRIALS):
//         if orders[i]==0:
//             if orders_2[i]==0:
//                 count["000111"]+=1
//             else:
//                 if moves[i] ==0:
//                     count["010110"]+=1
//                 else:
//                     count["000111"]+=1
//         elif orders[i]==1:
//             if moves[i] ==0:
//                 if moves_2[i] ==0:
//                     count["100110"]+=1
//                 else:
//                     count["100101"]+=1
//             else:
//                 count["000111"]+=1
//         else:
//             if moves[i] ==0:
//                 if orders_2[i]==0:
//                      count["010110"]+=1
//                 else:
//                     count["100110"]+=1
//             else:
//                 if orders_2[i]==0:
//                      count["000111"]+=1
//                 else:
//                     if moves_2[i]==0:
//                         count["100101"]+=1
//                     else:
//                        count["000111"]+=1
//     return count

// result = test()
// for key,value in result.items():
//     print(key,value/TRIALS)

int main(){
    auto rtest = test();
    std::cout<<"000111\t"<<double(rtest._000111)/TRIALS<<std::endl;
    std::cout<<"010110\t"<<double(rtest._010110)/TRIALS<<std::endl;
    std::cout<<"100101\t"<<double(rtest._100101)/TRIALS<<std::endl;
    std::cout<<"100110\t"<<double(rtest._100110)/TRIALS<<std::endl;
    return 0;
}