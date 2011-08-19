set PACKET_SIZE;

param source{i in PACKET_SIZE};
param target{j in PACKET_SIZE};

var morph{i in PACKET_SIZE, j in PACKET_SIZE};

minimize min_padding: sum{i in PACKET_SIZE, j in PACKET_SIZE} (source[j] * morph[i,j]*(abs(i - j)));

subject to morphing_creation {i in PACKET_SIZE} : sum{j in PACKET_SIZE} (morph[i,j]*source[j]) = target[i];
subject to column_prob {j in PACKET_SIZE}: sum{i in PACKET_SIZE} (morph[i,j]) = 1;
subject to a_ij_gte_0 {i in PACKET_SIZE, j in PACKET_SIZE}: (morph[i,j]) >= 0;

data;

set PACKET_SIZE 0 1 2 3 4; /* in bytes */

param source :=
    0 0.13361002060357148
    1 0.32861444073616064
    2 0.2272868609999894
    3 0.15618370377875351
    4 0.15430497388152506;
param target :=
    0 0.10981360310314769
    1 0.26513423659194113
    2 0.167047408114084
    3 0.028028772189415692
    4 0.42997598000141135;

end;
